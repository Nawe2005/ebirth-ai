# AI Future By eBirth — daily auto-drafter (100% Gemini, free-tier friendly)

Every morning this generates a Sinhala AI-news article + a matching image and
drops a **draft** into your private `#ai-drafts` Discord channel. You review it
on your phone, then tap one button to publish it to the public `#ai-updates`.

```
07:00 SLT ──► GitHub Actions ──► Google News (real headlines)
                                 └► Gemini writes Sinhala article (your style)
                                 └► Gemini makes the image (best-effort)
                                 └► preview posted to #ai-drafts   ← you review here
you tap "Publish draft" ──────► posted to #ai-updates             ← goes live
```

Nothing goes public without you pressing publish.

## Is it really free?
- **Article writing: yes, comfortably.** Gemini's free API tier is far more than
  one article a day needs.
- **Images: mostly, with a catch.** Gemini's current image API models are not
  clearly on a free tier anymore, and the cheap legacy one is being retired in
  Oct 2026. **Keep your Gemini key on the free tier (no card attached) and you
  can never be charged** — image generation will either work within free limits
  or fail, and if it fails this pipeline just posts the article as text so you
  add your own image at review time. Zero risk of a bill.
- Want images guaranteed, hands-off? Set `IMAGE_SOURCE = "none"` in
  `generate_draft.py` and attach your own image each day (make it free in the
  Gemini app / AI Studio, or drop `drafts/<date>.png` into the repo). Ask me and
  I can also wire in free stock images (Pexels/Unsplash) instead.

---

## One-time setup (~15 minutes)

### 1. Two Discord webhooks
Create a **private** `#ai-drafts` channel and keep your public `#ai-updates`.
For each: Channel → Edit Channel → Integrations → Webhooks → New Webhook →
**Copy Webhook URL**. You'll have two URLs.

### 2. One Gemini API key (free)
https://aistudio.google.com/apikey — do **not** attach a billing card; the free
tier is all you need and keeps costs at exactly zero.

### 3. Put these files in a GitHub repo
A **public** repo gives unlimited free Actions minutes; a private one gives
2,000 free min/month. This job uses ~2 min/day either way.

### 4. Add your secrets
Repo → Settings → Secrets and variables → Actions → New repository secret.
Add these three, names exactly as below:

| Secret name              | Value                          |
|--------------------------|--------------------------------|
| `GEMINI_API_KEY`         | your Gemini key                |
| `DISCORD_DRAFT_WEBHOOK`  | webhook URL for `#ai-drafts`   |
| `DISCORD_PUBLIC_WEBHOOK` | webhook URL for `#ai-updates`  |

### 5. Paste your past articles
Open `prompts/style_examples.txt` and paste 2–3 real articles. This is what
makes drafts sound like **you**. Do this before the first run.

### 6. Test it
Repo → Actions → **Generate daily draft** → Run workflow. A preview should
appear in `#ai-drafts` within a minute.

---

## Your daily routine (~1 minute)
1. Morning: a draft lands in `#ai-drafts`.
2. Read it on your phone.
3. Happy as-is? → GitHub app → Actions → **Publish draft** → Run workflow. Done.
4. Want edits? → open `drafts/<today>.md` in GitHub, edit, commit → then publish.
5. No auto image that day? → drop `drafts/<today>.png` into the repo before publishing.

---

## Tuning
- **Topics:** edit the `NEWS_RSS` query at the top of `generate_draft.py`.
- **Post time:** edit `cron` in `.github/workflows/draft.yml` (UTC; add 5h30m for SLT).
- **Length / tone:** adjust `MAX_WORDS` and the prompt in `generate_draft.py`.
- **Image on/off:** `IMAGE_SOURCE = "gemini"` or `"none"` in `generate_draft.py`.
- **Models:** `GEMINI_MODEL` / `GEMINI_IMAGE_MODEL` are near the top of the script.

## Notes
- Image models can't render readable text — these are clean conceptual
  illustrations, not the labelled infographics. Keep making those by hand.
- Drafts (`.md` + `.png`) are committed to the repo, so you get a free archive.
