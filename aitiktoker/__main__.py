"""Command line entry point.

    python -m aitiktoker formats
    python -m aitiktoker script products/sample_led_strip.json --format self_review
    python -m aitiktoker script products/sample_led_strip.json --format red_flag --dry-run
    python -m aitiktoker voice output/scripts/sample-led-strip__red_flag.json
    python -m aitiktoker voice output/scripts/sample-led-strip__red_flag.json --engine edge --voice th-TH-NiwatNeural
    python -m aitiktoker voice output/scripts/sample-led-strip__red_flag.json --compare
    python -m aitiktoker video output/scripts/sample-led-strip__red_flag.json
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from .formats import FORMATS
from .models import ProductBrief, VideoScript
from .script_writer import DEFAULT_MODELS, SYSTEM_PROMPT, build_prompt, check_script, generate_script


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()

    parser = argparse.ArgumentParser(prog="aitiktoker")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("formats", help="list comedy formats")
    script = sub.add_parser("script", help="write a script for one product")
    script.add_argument("brief", type=Path, help="product brief JSON file")
    script.add_argument("--format", default="self_review", choices=sorted(FORMATS))
    script.add_argument("--out", type=Path, default=Path("output/scripts"))
    script.add_argument("--dry-run", action="store_true", help="print the prompt without calling Gemini")
    voice = sub.add_parser("voice", help="make voice-over audio for a script (Gemini Puck by default)")
    voice.add_argument("script", type=Path, help="script JSON from the script command")
    voice.add_argument("--engine", choices=["edge", "gemini"], help="default: gemini")
    voice.add_argument("--voice", help="voice name; default: Puck for gemini, Premwadee for edge")
    voice.add_argument("--compare", action="store_true", help="make every voice of both engines to compare")
    voice.add_argument("--out", type=Path, default=Path("output/voice"))
    video = sub.add_parser("video", help="build a 9:16 video from a script and its voice-over")
    video.add_argument("script", type=Path, help="script JSON from the script command")
    video.add_argument("--audio", type=Path, help="default: the voice command's output for this script")
    video.add_argument("--brief", type=Path, help="product brief with photos; default: found in products/ by id")
    video.add_argument("--speed", type=float, default=1.15, help="narration speed-up, 1.0 = unchanged")
    video.add_argument("--out", type=Path, default=Path("output/video"))
    args = parser.parse_args()

    if args.command == "formats":
        for fmt in FORMATS.values():
            print(f"{fmt.id:22} {fmt.name}")
        return 0

    if args.command == "voice":
        return make_voices(args)

    if args.command == "video":
        return make_video(args)

    brief = ProductBrief.model_validate_json(args.brief.read_text(encoding="utf-8"))
    fmt = FORMATS[args.format]

    if args.dry_run:
        print(SYSTEM_PROMPT)
        print("-" * 60)
        print(build_prompt(brief, fmt))
        return 0

    client = _gemini_client()
    if client is None:
        return 1
    models = [m.strip() for m in os.getenv("GEMINI_MODELS", "").split(",") if m.strip()] or DEFAULT_MODELS
    try:
        result = generate_script(brief, fmt, client, models)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        print("Google's free tier is probably busy. Try again in a few minutes.", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"{brief.id}__{fmt.id}.json"
    out_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    print(f"HOOK: {result.hook}\n")
    for i, scene in enumerate(result.scenes, 1):
        print(f"[{i}] ({scene.duration_sec:g}s) {scene.voiceover}")
        print(f"    text: {scene.on_screen_text} | visual: {scene.visual}")
    print(f"\nCTA: {result.cta}")
    print(f"Caption: {result.caption} {' '.join('#' + h for h in result.hashtags)}")

    warnings = check_script(brief, result)
    if warnings:
        print("\nCHECK BEFORE USING:")
        for w in warnings:
            print(f"  - {w}")
    print(f"\nSaved to {out_file}")
    return 0


def make_voices(args: argparse.Namespace) -> int:
    from . import voice

    script = VideoScript.model_validate_json(args.script.read_text(encoding="utf-8"))
    text = voice.narration_text(script)
    out_dir = args.out / args.script.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.compare:
        jobs = [("edge", v) for v in voice.EDGE_VOICES] + [("gemini", v) for v in voice.GEMINI_VOICES]
    else:
        engine = args.engine or voice.DEFAULT_ENGINE
        default = voice.DEFAULT_VOICE if engine == voice.DEFAULT_ENGINE else voice.BACKUP_VOICE
        jobs = [(engine, args.voice or default)]
        # With no choices made, fall back to the backup voice so automation still gets audio.
        if not args.engine and not args.voice:
            jobs.append((voice.BACKUP_ENGINE, voice.BACKUP_VOICE))

    client = None
    failed = 0
    for engine, name in jobs:
        out_path = out_dir / f"{engine}-{name}"
        try:
            if engine == "edge":
                path = voice.edge_voice(text, name, out_path)
                print(f"{path}")
            else:
                if client is None:
                    client = _gemini_client()
                    if client is None:
                        return 1
                path, model = voice.gemini_voice(text, name, out_path, client)
                print(f"{path}  ({model})")
            if not args.compare:
                return 0
        except Exception as e:  # keep going so one bad voice doesn't stop the run
            failed += 1
            print(f"{engine} {name} failed: {e}", file=sys.stderr)
            if not args.compare and failed < len(jobs):
                print("Using the backup voice instead.", file=sys.stderr)
    return 1 if failed == len(jobs) else 0


def make_video(args: argparse.Namespace) -> int:
    from . import video, voice

    script = VideoScript.model_validate_json(args.script.read_text(encoding="utf-8"))
    audio = args.audio
    if audio is None:
        # Prefer the channel voice, then the backup voice the voice command falls back to.
        voice_dir = Path("output/voice") / args.script.stem
        candidates = [
            voice_dir / f"{voice.DEFAULT_ENGINE}-{voice.DEFAULT_VOICE}.wav",
            voice_dir / f"{voice.BACKUP_ENGINE}-{voice.BACKUP_VOICE}.mp3",
        ]
        audio = next((c for c in candidates if c.exists()), None)
        if audio is None:
            print(f"No voice-over found in {voice_dir}. Run the voice command first.", file=sys.stderr)
            return 1

    images = []
    brief_path = args.brief or _find_brief(args.script.stem.split("__")[0])
    if brief_path:
        brief = ProductBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
        images = [brief_path.parent / p for p in brief.images]
        missing = [str(p) for p in images if not p.exists()]
        if missing:
            print(f"Photos listed in {brief_path} not found: {', '.join(missing)}", file=sys.stderr)
            return 1

    out_path = args.out / f"{args.script.stem}.mp4"
    try:
        video.render(script, audio, out_path, images=images, speed=args.speed)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        print(f"Video failed: {e}", file=sys.stderr)
        return 1
    print(f"{out_path}  (voice: {audio.name}, photos: {len(images)})")
    return 0


def _find_brief(product_id: str) -> Path | None:
    """Script files are named <product id>__<format>.json, so look up the brief with that id."""
    for path in Path("products").glob("*.json"):
        try:
            if ProductBrief.model_validate_json(path.read_text(encoding="utf-8")).id == product_id:
                return path
        except ValueError:
            continue
    return None


def _gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is empty. Put your key from aistudio.google.com in .env.", file=sys.stderr)
        return None
    from google import genai

    return genai.Client(api_key=api_key)


if __name__ == "__main__":
    raise SystemExit(main())
