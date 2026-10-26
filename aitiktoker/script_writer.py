"""Writes a Thai comedy video script for one product with the Gemini API."""

import re
import sys

from google import genai
from google.genai import types

from .formats import ComedyFormat
from .gemini import call_with_fallback
from .models import ProductBrief, VideoScript

SYSTEM_PROMPT = """\
You write scripts for short, funny TikTok videos in Thai for a Gen Z / Gen Alpha audience in Thailand.

Voice and style:
- Natural spoken Thai like a Thai TikTok creator, not textbook Thai. Use current slang where it fits
  (for example ปังมาก, จึ้ง, ตัวมัม, ฉ่ำ, เกินต้าน, ของมันต้องมี, ตัวตึง), but keep it understandable.
- The hook must stop the scroll in the first 2 seconds: a bold claim, a question, or a weird situation.
- Short sentences. Every scene should have a joke, a twist or a reaction.
- Total length 20-40 seconds of narration, 4-7 scenes.

Honesty rules (never break these):
- Only state product facts that appear in the product brief. Do not invent features, numbers,
  reviews, awards, discounts or health/safety claims.
- If you mention the price, use exactly the price in the brief.
- Jokes and exaggeration about the viewer's life are fine; exaggeration about what the product does is not.
- List every product fact you used in facts_used.

End with an honest one-line value statement and a call to action to tap the yellow basket (ตะกร้าเหลือง).
"""


def build_prompt(brief: ProductBrief, fmt: ComedyFormat) -> str:
    return (
        f"Comedy format: {fmt.name}\n"
        f"Format instructions: {fmt.instructions}\n\n"
        f"Product brief (the only facts you may use):\n{brief.model_dump_json(indent=2, exclude={"images"})}\n"
    )


# Tried in order when a model is busy.
DEFAULT_MODELS = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
]


def generate_script(
    brief: ProductBrief, fmt: ComedyFormat, client: genai.Client, models: list[str]
) -> VideoScript:
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=VideoScript,
        temperature=1.0,
    )
    response, model = call_with_fallback(
        models,
        lambda m: client.models.generate_content(model=m, contents=build_prompt(brief, fmt), config=config),
    )
    print(f"Script written by {model}.", file=sys.stderr)
    return VideoScript.model_validate_json(response.text)


def check_script(brief: ProductBrief, script: VideoScript) -> list[str]:
    """Returns warnings for things a person should look at before the video is made."""
    warnings = []
    spoken = " ".join([script.hook, *(s.voiceover for s in script.scenes), script.cta])
    shown = " ".join(s.on_screen_text for s in script.scenes)

    for amount in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*บาท", spoken + " " + shown):
        if float(amount.replace(",", "")) != brief.price_thb:
            warnings.append(f"Mentions {amount} บาท but the brief's price is {brief.price_thb:g} บาท.")

    duration = sum(s.duration_sec for s in script.scenes)
    if not 15 <= duration <= 45:
        warnings.append(f"Total duration is {duration:g}s; aim for 15-45s.")

    known_facts = [brief.name, *brief.features, brief.notes, f"{brief.price_thb:g}"]
    for fact in script.facts_used:
        if _is_price(fact, brief.price_thb):
            continue
        # A fact must contain a whole brief item; a short fragment like "กันน้ำ" inside "ไม่กันน้ำ" doesn't count.
        if not any(f and f in fact for f in known_facts):
            warnings.append(f"Fact not found word-for-word in the brief, check it: {fact}")

    return warnings


def _is_price(fact: str, price: float) -> bool:
    """True for a bare price like "159", "159.0" or "159 บาท"."""
    number = fact.replace("บาท", "").replace(",", "").strip()
    try:
        return float(number) == price
    except ValueError:
        return False
