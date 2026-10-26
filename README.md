# AI-Tiktoker

Funny Thai TikTok videos about TikTok Shop affiliate products, made with AI. See [PLAN.md](PLAN.md) for the full plan.

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Put your free Gemini API key from https://aistudio.google.com in `.env`.

## Write a script

```bash
.venv\Scripts\python -m aitiktoker formats
.venv\Scripts\python -m aitiktoker script products/sample_led_strip.json --format red_flag
```

Scripts are saved to `output/scripts/`. Add `--dry-run` to see the prompt without calling Gemini.
Read the "CHECK BEFORE USING" warnings: they flag wrong prices and claims not found in the product brief.

## Make the voice-over

```bash
.venv\Scripts\python -m aitiktoker voice output/scripts/sample-led-strip__red_flag.json
```

The channel voice is Gemini TTS "Puck". If Gemini is busy or fails, it falls back to the free
edge-tts voice `th-TH-PremwadeeNeural`. Audio is saved to `output/voice/`.
Use `--engine edge` or `--voice <name>` to pick one yourself, or `--compare` to make every voice.

## Build the video

Needs FFmpeg (`winget install Gyan.FFmpeg`).

```bash
.venv\Scripts\python -m aitiktoker video output/scripts/sample-led-strip__red_flag.json
```

Makes a 1080x1920 MP4 in `output/video/` from the script, its voice-over (Puck, or the backup voice)
and the product photos. The product brief is found in `products/` by id, or pass `--brief`.
Narration is sped up to 1.15x by default; change it with `--speed`.

## Add a product

Copy `products/sample_led_strip.json`, then fill in the real facts from the product page.
The script only uses what's in this file, so put every feature you want mentioned in it.

List the product photos in `images`, relative to the brief file (for example
`images/my-product/1.jpg`). The video shows them one per scene in turn, with a slow zoom.
Use photos you're allowed to use, such as the seller's listing photos or your own.
The sample product uses placeholder test patterns.
