"""Builds a 9:16 TikTok video from a script, its voice-over and product photos with FFmpeg.

Colored backgrounds, big on-screen text and captions are drawn by ASS subtitle files, because libass shapes
Thai correctly (tone marks and vowels sit in the right place). Photos are layered between the background
and the text, one per scene in turn, with a slow zoom.
"""

import glob
import os
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .models import VideoScript

WIDTH, HEIGHT, FPS = 1080, 1920, 30
FONT = "Leelawadee UI"  # ships with Windows and covers Thai

# ASS colors are &HBBGGRR. Bright backgrounds that rotate per scene; the call to action is yellow.
SCENE_COLORS = ["&H7F3DFF", "&HE0408B", "&HB09A00", "&H1E8CFF", "&H8E44AD"]
CTA_COLOR = "&H00D4FF"

BIG_LINE_CHARS = 12  # big on-screen text, per line, when it has the screen to itself
BIG_TOP_LINE_CHARS = 14  # smaller big text above a photo
CAPTION_CHARS = 22  # one caption chunk at the bottom

# Photos sit in a square box between the big text (top) and the captions (bottom).
PHOTO_BOX, PHOTO_TOP, PHOTO_BORDER = 760, 600, 12
PHOTO_ZOOM = 0.08  # how far the slow zoom goes over one scene

ASS_HEADER = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, \
Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, \
MarginV, Encoding
Style: Bg,{FONT},10,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Big,{FONT},110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,4,5,80,80,0,1
Style: BigTop,{FONT},88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,4,8,60,60,0,1
Style: CtaBig,{FONT},120,&H00000000,&H00000000,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,5,80,80,0,1
Style: CtaBigTop,{FONT},96,&H00000000,&H00000000,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,8,60,60,0,1
Style: Caption,{FONT},72,&H0000E6FF,&H0000E6FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,80,160,430,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


@dataclass
class Segment:
    """One stretch of the video: what is said, the big text on screen and the background."""

    spoken: str
    big_text: str
    color: str
    is_cta: bool = False
    start: float = 0.0
    end: float = 0.0


def timeline(script: VideoScript, total_sec: float) -> list[Segment]:
    """Times each segment by how much text is spoken in it, since narration speed is roughly even."""
    parts = [Segment(script.hook, script.hook, SCENE_COLORS[0])]
    for i, scene in enumerate(script.scenes, 1):
        parts.append(Segment(scene.voiceover, scene.on_screen_text, SCENE_COLORS[i % len(SCENE_COLORS)]))
    parts.append(Segment(script.cta, "กดตะกร้าเหลือง เลย!", CTA_COLOR, is_cta=True))

    weights = [max(_spoken_len(p.spoken), 1) for p in parts]
    sec_per_unit = total_sec / sum(weights)
    t = 0.0
    for part, weight in zip(parts, weights):
        part.start, part.end = t, t + weight * sec_per_unit
        t = part.end
    return parts


def background_ass(parts: list[Segment]) -> str:
    box = f"m 0 0 l {WIDTH} 0 {WIDTH} {HEIGHT} 0 {HEIGHT}"
    return ASS_HEADER + "\n".join(
        _event(0, p.start, p.end, "Bg", f"{{\\an7\\pos(0,0)\\p1\\c{p.color}&}}{box}") for p in parts
    ) + "\n"


def text_ass(parts: list[Segment], with_photos: bool) -> str:
    lines = []
    pop = "{\\fscx70\\fscy70\\t(0,160,\\fscx100\\fscy100)}"
    for part in parts:
        if with_photos:
            style = "CtaBigTop" if part.is_cta else "BigTop"
            wrapped = _wrap(part.big_text, BIG_TOP_LINE_CHARS)
            size = ""
            # Long text (usually the hook) would run into the photo, so shrink it and fit more per line.
            if len(wrapped) > 3:
                wrapped = _wrap(part.big_text, BIG_TOP_LINE_CHARS * 4 // 3)
                size = "\\fs66"
            big = "\\N".join(wrapped)
            pos = f"{{\\pos({WIDTH // 2},140){size}}}"
        else:
            style = "CtaBig" if part.is_cta else "Big"
            big = "\\N".join(_wrap(part.big_text, BIG_LINE_CHARS))
            pos = f"{{\\pos({WIDTH // 2},{HEIGHT * 2 // 5})}}"
        lines.append(_event(1, part.start, part.end, style, pos + pop + big))

        chunks = _wrap(part.spoken, CAPTION_CHARS)
        chunk_weights = [max(_spoken_len(c), 1) for c in chunks]
        # Yellow captions vanish on the yellow call-to-action card, so use white there.
        caption_color = "{\\c&HFFFFFF&}" if part.is_cta else ""
        t = part.start
        for chunk, w in zip(chunks, chunk_weights):
            dur = (part.end - part.start) * w / sum(chunk_weights)
            lines.append(_event(2, t, t + dur, "Caption", caption_color + chunk))
            t += dur
    return ASS_HEADER + "\n".join(lines) + "\n"


def render(
    script: VideoScript, audio: Path, out_path: Path, images: list[Path] = [], speed: float = 1.15
) -> Path:
    """Speeds the narration up a little (TikTok pace), layers background, photos and text, writes an MP4."""
    ffmpeg = find_ffmpeg()
    total_sec = audio_duration(audio, ffmpeg) / speed
    parts = timeline(script, total_sec)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg_ass, text_ass_path = out_path.with_suffix(".bg.ass"), out_path.with_suffix(".text.ass")
    bg_ass.write_text(background_ass(parts), encoding="utf-8")
    text_ass_path.write_text(text_ass(parts, with_photos=bool(images)), encoding="utf-8")

    inputs = ["-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}", "-i", str(audio.resolve())]
    graph = [f"[0:v]subtitles={bg_ass.name}[base0]"]
    for i, part in enumerate(parts if images else []):
        image = images[i % len(images)]
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{part.end - part.start + 0.1:.3f}",
                   "-i", str(image.resolve())]
        graph += _photo_filters(i, 2 + i, part, image_size(image, ffmpeg))
    last = f"base{len(parts) if images else 0}"
    graph += [f"[{last}]subtitles={text_ass_path.name}[v]", f"[1:a]atempo={speed}[a]"]

    # The subtitles filter can't take Windows drive letters, so run FFmpeg next to the .ass files.
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *inputs,
            "-filter_complex", ";".join(graph),
            "-map", "[v]", "-map", "[a]", "-t", f"{total_sec:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            out_path.name,
        ],
        cwd=out_path.parent,
        check=True,
    )
    return out_path


def _photo_filters(i: int, input_index: int, part: Segment, size: tuple[int, int]) -> list[str]:
    """Fits the photo in the box, zooms in slowly, adds a white border and shows it only during its scene."""
    w, h = _fit(size, PHOTO_BOX)
    frames = max(round((part.end - part.start) * FPS), 1)
    # zoompan jitters on small images, so give it double resolution to work from.
    zoom = (
        f"scale={w * 2}:{h * 2},"
        f"zoompan=z='1+{PHOTO_ZOOM}*on/{frames}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={FPS},"
        f"pad={w + 2 * PHOTO_BORDER}:{h + 2 * PHOTO_BORDER}:{PHOTO_BORDER}:{PHOTO_BORDER}:white,"
        f"setpts=PTS-STARTPTS+{part.start:.3f}/TB"
    )
    x = (WIDTH - w) // 2 - PHOTO_BORDER
    y = PHOTO_TOP + (PHOTO_BOX - h) // 2 - PHOTO_BORDER
    return [
        f"[{input_index}:v]{zoom}[photo{i}]",
        f"[base{i}][photo{i}]overlay={x}:{y}:enable='between(t,{part.start:.3f},{part.end:.3f})'"
        f":eof_action=pass[base{i + 1}]",
    ]


def _fit(size: tuple[int, int], box: int) -> tuple[int, int]:
    """Largest even width and height that fit in a box x box square, keeping the photo's shape."""
    w, h = size
    scale = box / max(w, h)
    return round(w * scale / 2) * 2, round(h * scale / 2) * 2


def image_size(image: Path, ffmpeg: str) -> tuple[int, int]:
    out = subprocess.run(
        [_ffprobe(ffmpeg), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(image)],
        capture_output=True, text=True, check=True,
    )
    w, h = out.stdout.strip().split(",")[:2]
    return int(w), int(h)


def find_ffmpeg() -> str:
    """FFmpeg from PATH, or from the winget install folder when PATH hasn't refreshed yet."""
    found = os.getenv("FFMPEG") or shutil.which("ffmpeg")
    if not found:
        pattern = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe")
        found = next(iter(sorted(glob.glob(pattern))), None)
    if not found:
        raise RuntimeError("FFmpeg not found. Install it with: winget install Gyan.FFmpeg")
    return found


def audio_duration(audio: Path, ffmpeg: str) -> float:
    out = subprocess.run(
        [_ffprobe(ffmpeg), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _ffprobe(ffmpeg: str) -> str:
    return str(Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix))


def _event(layer: int, start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}"


def _ts(sec: float) -> str:
    cs = round(sec * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _spoken_len(text: str) -> int:
    """Characters that take time to say: skips spaces and Thai marks that sit above or below a letter."""
    return sum(1 for ch in text if not ch.isspace() and unicodedata.category(ch) != "Mn")


def _wrap(text: str, max_chars: int) -> list[str]:
    """Splits text into lines at spaces; Thai runs with no spaces are cut between letters, never before a mark."""
    text = text.replace("{", "(").replace("}", ")").replace("\\", "/")
    lines: list[str] = []
    current = ""
    for word in text.split():
        for piece in _cut(word, max_chars):
            candidate = f"{current} {piece}".strip()
            if current and _spoken_len(candidate) > max_chars:
                lines.append(current)
                current = piece
            else:
                current = candidate
    if current:
        lines.append(current)
    return lines


THAI_LEADING_VOWELS = set("เแโใไ")
THAI_NO_BREAK_BEFORE = set("ะาำๆ!?.,:;)")


def _cut(word: str, max_chars: int) -> list[str]:
    pieces, current = [], ""
    for ch in word:
        can_break = (
            unicodedata.category(ch) != "Mn"
            and ch not in THAI_NO_BREAK_BEFORE
            and current[-1:] not in THAI_LEADING_VOWELS
        )
        if current and can_break and _spoken_len(current) >= max_chars:
            pieces.append(current)
            current = ""
        current += ch
    return pieces + [current] if current else pieces
