"""Writes a Thai comedy video script for one product with the Gemini API."""

import re
import sys
import time

from google import genai
from google.genai import errors, types

from .formats import ComedyFormat
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
        f"Product brief (the only facts you may use):\n{brief.model_dump_json(indent=2)}\n"
    )


# Tried in order. Free-tier keys often get "high demand" errors, so a busy model falls through to the next.
DEFAULT_MODELS = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
]

# Overloaded or rate limited: worth waiting and trying again.
RETRYABLE_CODES = {429, 500, 503, 504}


def generate_script(
    brief: ProductBrief,
    fmt: ComedyFormat,
    client: genai.Client,
    models: list[str],
    attempts_per_model: int = 3,
    first_wait_sec: float = 2.0,
) -> VideoScript:
    """Tries each model in turn, retrying busy ones with growing waits (2s, 4s, ...)."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=VideoScript,
        temperature=1.0,
    )
    last_error: Exception | None = None

    for model in models:
        for attempt in range(1, attempts_per_model + 1):
            try:
                response = client.models.generate_content(
                    model=model, contents=build_prompt(brief, fmt), config=config
                )
                print(f"Script written by {model}.", file=sys.stderr)
                return VideoScript.model_validate_json(response.text)
            except errors.APIError as e:
                last_error = e
                if e.code not in RETRYABLE_CODES:
                    print(f"{model}: {e.code} {e.status}, skipping this model.", file=sys.stderr)
                    break
                if attempt == attempts_per_model:
                    print(f"{model}: still busy after {attempt} tries, moving on.", file=sys.stderr)
                    break
                wait = first_wait_sec * 2 ** (attempt - 1)
                print(f"{model}: {e.code} {e.status}, retrying in {wait:g}s...", file=sys.stderr)
                time.sleep(wait)

    raise RuntimeError(f"Every model failed. Last error: {last_error}")


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
