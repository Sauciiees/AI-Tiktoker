# AI-Tiktoker — Project Plan

## Goal

Earn TikTok Shop affiliate commission with short, funny, **Thai-language** videos about
products, aimed at Gen Z / Gen Alpha. The system should eventually go from
"pick a product" to "video posted" with as little manual work as possible.

## Ground rules

1. **Zero cost to start.** Free API tiers and local tools only. Paid tools are optional upgrades.
2. **Quality over volume.** TikTok suppresses mass-produced, unoriginal content. Aim for 1–3 good
   videos a day, not 30 copies.
3. **Honest claims only.** Scripts may only use facts from the product brief. No invented
   features, fake reviews or health claims.
4. **Label AI content.** Turn on TikTok's "AI-generated content" label on every video.
5. **Human review gate.** A person approves each video before it's posted, at least until the
   formats are proven.

## Known constraints

- TikTok Shop affiliate needs a minimum follower count (varies by country). Until then the goal is
  growing followers.
- TikTok's Content Posting API needs an approved developer app; unaudited apps can only post
  private videos. The API may not support attaching Shop product links, so tagging the product
  could stay a manual step. Verify when we build the publisher.
- The Google AI Pro subscription (Gemini app) is separate from the Gemini API. The pipeline uses a
  free Gemini API key from Google AI Studio; the subscription is used by hand for creative assets.

## Pipeline

```
1. Product scout   → choose trending, high-commission, visual products
2. Product brief   → JSON: name, price, features, images, audience (facts only)
3. Script writer   → Gemini writes a Thai script in one of our comedy formats
4. Voice           → Thai text-to-speech
5. Visuals         → product photos + motion, stickers, text, reusable intro/outro clips
6. Editor          → 9:16 video with captions and music
7. Review gate     → approve or reject
8. Publisher       → upload (manual first, API later), AI label, product tag
9. Analytics       → views, watch time, clicks, sales per format → feeds back into 1 and 3
```

## Free stack

| Part | Tool |
|---|---|
| Language | Python 3.12 |
| Scripts | Gemini API (free tier, key from aistudio.google.com) |
| Voice | Gemini TTS voice "Puck" (free tier); edge-tts `th-TH-PremwadeeNeural` as backup |
| Editing | FFmpeg + MoviePy |
| Captions | faster-whisper (local) |
| Scheduling | Windows Task Scheduler |
| Manual creative | Google AI Pro: mascot images, intro/outro clips, format brainstorming |

## Comedy formats (first set)

Defined in `aitiktoker/formats.py`.

1. **Product reviews itself** – the product talks in first person with a dramatic personality.
2. **Red flag / green flag** – rate the product like a situationship.
3. **Villain origin story** – dramatic narrator: life before the product was a tragedy.
4. **Group chat drama** – products arguing in a fake chat.
5. **Gen Alpha translator** – explain in pure slang, then "translate for millennials".
6. **Sports commentator** – hyped play-by-play of someone using the product.
7. **NPC vs main character** – life without vs with the product.

Every format ends with an honest one-liner on price/value and a call to action to the yellow basket.

## Roadmap

- **Phase 1 – MVP:** product brief → script (done first) → voice → video, run by hand. Test 3–4 formats.
- **Phase 2 – Semi-automatic:** batch generation, review page, scheduled uploads as drafts.
- **Phase 3 – Feedback loop:** pull analytics, score formats and products.
- **Phase 4 – Full auto with guardrails:** auto-post approved videos at 1–3 per day.

## Status

- [x] Repo created
- [x] Script generator (Gemini, Thai, structured JSON output)
- [x] Thai voice-over (Gemini TTS "Puck", edge-tts Premwadee as backup)
- [x] Video assembly v1 (color cards, big text, timed captions)
- [x] Product photos in the video (one per scene, slow zoom)
- [ ] Word-accurate captions (faster-whisper)
- [ ] Review step
- [ ] Publisher
- [ ] Analytics
