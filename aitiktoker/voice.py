"""Turns a video script into Thai voice-over audio with edge-tts or Gemini TTS."""

import io
import re
import wave
from pathlib import Path

import edge_tts
from google import genai
from google.genai import types

from .gemini import call_with_fallback
from .models import VideoScript

EDGE_VOICES = ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"]

# Prebuilt Gemini voices that suit a playful creator: Puck is upbeat, Zephyr bright, Leda youthful.
GEMINI_VOICES = ["Puck", "Zephyr", "Leda"]

# The channel's voice, picked by listening to all of the above. Edge is the backup when Gemini is busy.
DEFAULT_ENGINE, DEFAULT_VOICE = "gemini", "Puck"
BACKUP_ENGINE, BACKUP_VOICE = "edge", "th-TH-PremwadeeNeural"
GEMINI_TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview"]

# Gemini TTS follows a spoken-style instruction before the text.
GEMINI_STYLE = (
    "Read this Thai TikTok voice-over like an energetic, playful Thai Gen Z creator "
    "talking to friends, slightly fast, with fun emphasis on the jokes:"
)


def narration_text(script: VideoScript) -> str:
    """Hook, every scene's voice-over and the call to action, in speaking order."""
    return "\n".join([script.hook, *(s.voiceover for s in script.scenes), script.cta])


def edge_voice(text: str, voice: str, out_path: Path, rate: str = "+10%") -> Path:
    """Free Microsoft Edge voices. Saves an MP3."""
    out_path = out_path.with_suffix(".mp3")
    edge_tts.Communicate(text, voice, rate=rate).save_sync(str(out_path))
    return out_path


def gemini_voice(
    text: str, voice: str, out_path: Path, client: genai.Client, models: list[str] = GEMINI_TTS_MODELS
) -> tuple[Path, str]:
    """Gemini TTS with a style instruction. Saves a WAV; returns the path and the model used."""
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
        ),
    )
    response, model = call_with_fallback(
        models,
        lambda m: client.models.generate_content(model=m, contents=f"{GEMINI_STYLE}\n{text}", config=config),
    )
    audio = response.candidates[0].content.parts[0].inline_data
    out_path = out_path.with_suffix(".wav")
    out_path.write_bytes(_as_wav(audio.data, audio.mime_type))
    return out_path, model


def _as_wav(data: bytes, mime_type: str) -> bytes:
    """Newer models return WAV; older ones return raw 16-bit PCM like "audio/l16; rate=24000"."""
    if mime_type == "audio/wav" or data[:4] == b"RIFF":
        return data
    rate = re.search(r"rate=(\d+)", mime_type)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate.group(1)) if rate else 24000)
        w.writeframes(data)
    return buf.getvalue()
