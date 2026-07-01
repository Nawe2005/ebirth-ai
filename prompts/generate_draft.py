"""
generate_draft.py
-----------------
Runs every morning on GitHub Actions. 100% Gemini, free-tier friendly.

  1. Pulls today's real AI headlines from Google News RSS (free, no key).
  2. Asks Gemini to write ONE short Sinhala article grounded in those headlines,
     in your channel's style (from prompts/style_examples.txt).
  3. Asks Gemini to generate a matching illustration (best-effort — see notes).
  4. Saves the draft to drafts/<date>.md and drafts/<date>.png.
  5. Posts a preview to your PRIVATE #ai-drafts channel via webhook.

Nothing is published to the public channel here. publish.py does that, after
you review.

COST: Keep your Gemini key on the FREE tier (no card attached) and you can
never be charged. Article writing is well inside the free limits. Image
generation may hit a free-tier limit — if it does, this script just skips the
image and the draft still goes out with text, so you attach your own image at
review time. Zero risk of a bill.
"""

import os
import re
import json
import base64
import datetime

import requests
import feedparser
from google import genai
from google.genai import types

# ----------------------------------------------------------------------------
# CONFIG — tweak freely
# ----------------------------------------------------------------------------
NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q=(artificial+intelligence)+OR+(OpenAI)+OR+(Anthropic)+OR+(Google+AI)+when:1d"
    "&hl=en-US&gl=US&ceid=US:en"
)
MAX_HEADLINES = 8
GEMINI_MODEL = "gemini-2.5-flash"            # article writing (free tier is plenty)

# Image options:
#   "gemini" = try to generate an image with Gemini (free-tier best-effort)
#   "none"   = skip auto image; you drop drafts/<date>.png yourself before publishing
IMAGE_SOURCE = "gemini"
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"   # "Nano Banana". Replacement when it
                                                # retires (Oct 2026): gemini-3.1-flash-image-preview

BRAND_PURPLE = 0x5B2A86
MAX_WORDS = 300

# ----------------------------------------------------------------------------
# Secrets (GitHub → Settings → Secrets and variables → Actions)
# ----------------------------------------------------------------------------
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DRAFT_WEBHOOK = os.environ["DISCORD_DRAFT_WEBHOOK"]


def fetch_headlines() -> str:
    feed = feedparser.parse(NEWS_RSS)
    if not feed.entries:
        raise RuntimeError("No news returned from RSS — check the NEWS_RSS query.")
    lines = []
    for entry in feed.entries[:MAX_HEADLINES]:
        summary = re.sub("<[^<]+?>", "", getattr(entry, "summary", "")).strip()
        lines.append(f"- {entry.title}\n  {summary[:300]}\n  ({entry.link})")
    return "\n".join(lines)


def load_style_examples() -> str:
    with open("prompts/style_examples.txt", encoding="utf-8") as f:
        return f.read()


def write_article(headlines: str, style: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""You are the writer for "AI Future By eBirth", a Sinhala-language
AI news channel on Discord for a Sri Lankan audience.

TODAY'S REAL AI HEADLINES (only use facts that appear here — do NOT invent
anything, do NOT add statistics or quotes that are not present):
{headlines}

STYLE EXAMPLES — copy this tone, structure and length exactly:
{style}

TASK: Pick the single most important / interesting story from the headlines
above and write ONE short article about it.

RULES:
- Write in natural, conversational Sinhala.
- Keep English technical terms in English (AI, Machine Learning, GPU, API, etc.).
- Mobile-friendly: short paragraphs, a few bullet points, under {MAX_WORDS} words.
- Start with a bold title line.
- Ground every claim in the headlines above. If unsure, leave it out.

At the very end, on its own final line, output an image brief like this:
IMAGE_PROMPT: <one vivid English sentence describing an editorial illustration
for this story. Conceptual and clean. Do NOT put any words or text in the image.>
"""
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return resp.text.strip()


def split_article(raw: str):
    if "IMAGE_PROMPT:" in raw:
        body, image_prompt = raw.rsplit("IMAGE_PROMPT:", 1)
    else:
        body, image_prompt = raw, "A clean modern editorial illustration about AI technology, no text."
    body = body.strip()
    image_prompt = image_prompt.strip()
    first_line = next((l for l in body.splitlines() if l.strip()), "AI Update")
    title = re.sub(r"[#*_`]", "", first_line).strip()[:250]
    return title, body, image_prompt


def make_image(image_prompt: str):
    """Best-effort Gemini image generation. Returns bytes, or None on any failure
    (e.g. free-tier limit) so the draft still goes out with text only."""
    if IMAGE_SOURCE == "none":
        return None
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=f"Generate an illustration: {image_prompt}",
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        for part in resp.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                if isinstance(data, str):        # some SDK versions return base64
                    data = base64.b64decode(data)
                return data
        print("No image part returned by Gemini; posting text only.")
    except Exception as e:
        print(f"Image generation skipped ({e}); posting text only.")
    return None


def post_preview(title, body, image_bytes, date_str):
    embed = {
        "title": title[:256],
        "description": body[:4000],
        "color": BRAND_PURPLE,
        "footer": {"text": "AI Future By eBirth · draft preview"},
    }
    payload = {
        "content": (
            f"\U0001F7E3 **DRAFT for {date_str}** — review this, then go to GitHub → "
            f"Actions → **Publish draft** → Run workflow to send it to #ai-updates. "
            f"(Edit drafts/{date_str}.md first if you want changes.)"
        ),
        "embeds": [embed],
    }
    if image_bytes:
        embed["image"] = {"url": "attachment://image.png"}
        files = {
            "payload_json": (None, json.dumps(payload)),
            "files[0]": ("image.png", image_bytes, "image/png"),
        }
    else:
        payload["content"] += "\n\u26A0\uFE0F No auto image this time — drop drafts/" \
                              f"{date_str}.png into the repo before publishing if you want one."
        files = {"payload_json": (None, json.dumps(payload))}
    r = requests.post(DRAFT_WEBHOOK, files=files, timeout=60)
    r.raise_for_status()


def main():
    date_str = datetime.date.today().isoformat()
    print("Fetching headlines...")
    headlines = fetch_headlines()

    print("Writing article with Gemini...")
    raw = write_article(headlines, load_style_examples())
    title, body, image_prompt = split_article(raw)
    print(f"Title: {title}")
    print(f"Image prompt: {image_prompt}")

    print("Generating image with Gemini...")
    image_bytes = make_image(image_prompt)

    os.makedirs("drafts", exist_ok=True)
    with open(f"drafts/{date_str}.md", "w", encoding="utf-8") as f:
        f.write(body)
    if image_bytes:
        with open(f"drafts/{date_str}.png", "wb") as f:
            f.write(image_bytes)

    print("Posting preview to #ai-drafts...")
    post_preview(title, body, image_bytes, date_str)
    print("Done. Draft saved and preview posted.")


if __name__ == "__main__":
    main()
