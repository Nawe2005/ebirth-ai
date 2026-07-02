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
import time
import base64
import datetime
import requests
import feedparser
from google import genai

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

# Image options (all free):
#   "auto"        = try Gemini first, fall back to Pollinations if it returns nothing
#   "gemini"      = Gemini only (no fallback)
#   "pollinations"= free AI image, no key, always available
#   "none"        = skip auto image; you drop drafts/<date>.png yourself
IMAGE_SOURCE = "auto"

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"   # Replacement when it
                                                # retires (Oct 2026): gemini-3.1-flash-image-preview

BRAND_PURPLE = 0x5B2A86
MAX_WORDS = 300

# Retry settings for transient Gemini 503 / overload errors
GEMINI_MAX_RETRIES = 5
GEMINI_RETRY_DELAY = 15   # seconds between retries (doubles each time)

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


def _gemini_generate_with_retry(client, model, contents, config=None):
      """Call client.models.generate_content with exponential-backoff retry on 503."""
    delay = GEMINI_RETRY_DELAY
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
              try:
                            kwargs = {"model": model, "contents": contents}
                            if config is not None:
                                              kwargs["config"] = config
                                          return client.models.generate_content(**kwargs)
except Exception as e:
            err_str = str(e)
            is_overload = ("503" in err_str or "UNAVAILABLE" in err_str or
                                                      "high demand" in err_str or "429" in err_str or
                                                      "RESOURCE_EXHAUSTED" in err_str)
            if is_overload and attempt < GEMINI_MAX_RETRIES:
                              print(f"Gemini overloaded (attempt {attempt}/{GEMINI_MAX_RETRIES}). "
                                                          f"Retrying in {delay}s... ({e})")
                              time.sleep(delay)
                              delay = min(delay * 2, 120)
else:
                raise


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
    resp = _gemini_generate_with_retry(client, GEMINI_MODEL, prompt)
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


def geminiimage(image_prompt: str):
      """Ask Gemini for an image. Returns bytes or None."""
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)
    config = types.GenerateContentConfig(response_modalities=["IMAGE"])
    resp = _gemini_generate_with_retry(
              client, GEMINI_IMAGE_MODEL,
              f"Generate an illustration: {image_prompt}",
              config=config,
    )
    for part in resp.candidates[0].content.parts:
              inline = getattr(part, "inline_data", None)
              if inline and inline.data:
                            data = inline.data
                            if isinstance(data, str):            # some SDK versions return base64
                                data = base64.b64decode(data)
                                          return data
                                  return None


def pollinationsimage(image_prompt: str):
      """Free, no-key AI image (Flux via Pollinations). Returns bytes or None."""
    import urllib.parse
    url = "https://gen.pollinations.ai/image/" + urllib.parse.quote(image_prompt)
    r = requests.get(url, params={"width": 1280, "height": 720, "model": "flux"}, timeout=180)
    r.raise_for_status()
    if r.headers.get("content-type", "").startswith("image"):
              return r.content
          return None


def make_image(image_prompt: str):
      """Get an image for the article. Tries Gemini, then a free fallback, then
          gives up gracefully so the draft still goes out with text only."""
    if IMAGE_SOURCE == "none":
              return None

    # 1) Gemini first (unless pollinations-only was chosen)
    if IMAGE_SOURCE in ("auto", "gemini"):
              try:
                            data = geminiimage(image_prompt)
                            if data:
                                              print("Image: generated by Gemini.")
                                              return data
                                          print("Gemini returned no image.")
except Exception as e:
            print(f"Gemini image failed ({e}).")
        if IMAGE_SOURCE == "gemini":
                      return None                          # gemini-only: no fallback

    # 2) Free fallback (or the primary source if IMAGE_SOURCE == "pollinations")
    try:
              data = pollinationsimage(image_prompt)
              if data:
                            print("Image: generated by Pollinations (free).")
                            return data
                        print("Pollinations returned no image.")
except Exception as e:
        print(f"Fallback image failed ({e}); posting text only.")

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
                            f"\U0001F7E3 DRAFT for {date_str} — review this, then go to GitHub → "
                            f"Actions → Publish draft → Run workflow to send it to #ai-updates. "
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
