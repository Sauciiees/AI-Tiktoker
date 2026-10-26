"""Command line entry point.

    python -m aitiktoker formats
    python -m aitiktoker script products/sample_led_strip.json --format self_review
    python -m aitiktoker script products/sample_led_strip.json --format red_flag --dry-run
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .formats import FORMATS
from .models import ProductBrief
from .script_writer import SYSTEM_PROMPT, build_prompt, check_script, generate_script


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
    args = parser.parse_args()

    if args.command == "formats":
        for fmt in FORMATS.values():
            print(f"{fmt.id:22} {fmt.name}")
        return 0

    brief = ProductBrief.model_validate_json(args.brief.read_text(encoding="utf-8"))
    fmt = FORMATS[args.format]

    if args.dry_run:
        print(SYSTEM_PROMPT)
        print("-" * 60)
        print(build_prompt(brief, fmt))
        return 0

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is empty. Put your key from aistudio.google.com in .env.", file=sys.stderr)
        return 1

    from google import genai

    client = genai.Client(api_key=api_key)
    result = generate_script(brief, fmt, client, os.getenv("GEMINI_MODEL", "gemini-flash-latest"))

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


if __name__ == "__main__":
    raise SystemExit(main())
