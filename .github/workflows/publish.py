"""
publish.py
----------
Triggered manually (GitHub → Actions → Publish draft → Run workflow) once you
have reviewed — and optionally edited — the draft in #ai-drafts.

Reads drafts/<date>.md + drafts/<date>.png and posts them to the PUBLIC
#ai-updates channel via webhook. If no date is given, it publishes the most
recent draft.
"""

import os
import re
import json
import glob
import datetime

import requests

BRAND_PURPLE = 0x5B2A86
PUBLIC_WEBHOOK = os.environ["DISCORD_PUBLIC_WEBHOOK"]
# Optional YYYY-MM-DD passed from the workflow input; blank = latest.
REQUESTED_DATE = os.environ.get("DRAFT_DATE", "").strip()


def pick_draft():
    if REQUESTED_DATE:
        md = f"drafts/{REQUESTED_DATE}.md"
        png = f"drafts/{REQUESTED_DATE}.png"
        if not os.path.exists(md):
            raise FileNotFoundError(f"No draft found for {REQUESTED_DATE}")
        return REQUESTED_DATE, md, png
    md_files = sorted(glob.glob("drafts/*.md"))
    if not md_files:
        raise FileNotFoundError("No drafts found.")
    latest = md_files[-1]
    date_str = os.path.splitext(os.path.basename(latest))[0]
    return date_str, latest, f"drafts/{date_str}.png"


def main():
    date_str, md_path, png_path = pick_draft()
    with open(md_path, encoding="utf-8") as f:
        body = f.read().strip()

    first_line = next((l for l in body.splitlines() if l.strip()), "AI Update")
    title = re.sub(r"[#*_`]", "", first_line).strip()[:256]

    payload = {
        "embeds": [{
            "title": title,
            "description": body[:4000],
            "color": BRAND_PURPLE,
            "footer": {"text": "AI Future By eBirth"},
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }],
    }

    files = {"payload_json": (None, json.dumps(payload))}
    if os.path.exists(png_path):
        with open(png_path, "rb") as f:
            image_bytes = f.read()
        payload["embeds"][0]["image"] = {"url": "attachment://image.png"}
        files["payload_json"] = (None, json.dumps(payload))
        files["files[0]"] = ("image.png", image_bytes, "image/png")

    r = requests.post(PUBLIC_WEBHOOK, files=files, timeout=60)
    r.raise_for_status()
    print(f"Published draft {date_str} to #ai-updates.")


if __name__ == "__main__":
    main()
