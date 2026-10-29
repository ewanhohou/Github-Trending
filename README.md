# GitHub Trending Report

**English** | [繁體中文](README.zh-TW.md)

[![Live report](https://img.shields.io/badge/Live_report-ewanhohou.github.io-2ea44f?logo=github)](https://ewanhohou.github.io/Github-Trending/en/)
[![Trending report](https://github.com/ewanhohou/Github-Trending/actions/workflows/report.yml/badge.svg)](https://github.com/ewanhohou/Github-Trending/actions/workflows/report.yml)

**👉 See today's trending repos: <https://ewanhohou.github.io/Github-Trending/en/>**

| | English | 繁體中文 |
|---|---|---|
| Home | [All reports](https://ewanhohou.github.io/Github-Trending/en/) | [所有報告](https://ewanhohou.github.io/Github-Trending/) |
| Latest daily | [en/daily/latest](https://ewanhohou.github.io/Github-Trending/en/daily/latest.html) | [daily/latest](https://ewanhohou.github.io/Github-Trending/daily/latest.html) |
| Latest weekly | [en/weekly/latest](https://ewanhohou.github.io/Github-Trending/en/weekly/latest.html) | [weekly/latest](https://ewanhohou.github.io/Github-Trending/weekly/latest.html) |

Every day this scans [GitHub Trending](https://github.com/trending) and sums up each hot repo: what it is, what it's for, and its highlights, with an image when there is one. The report is published to GitHub Pages and announced on Telegram. On a phone you can add it to your home screen and use it like an app.

## Features

- Daily report: 08:30 Taipei time (00:30 UTC), top 25 across all languages
- Weekly picks: Sundays at 09:00 Taipei time, top 10 of the week plus the repos that showed up most often on the daily list
- Daily pick: one standout repo a day, never repeated within 90 days, sent to Telegram as a ready-to-post Threads card
  - Rules shortlist the top 5 (today's stars, AI-related, first time on the list, brand-new repos; lists and tutorials rank lower), then Workers AI picks one and says why
  - A 1080×1350 dark card (the Threads / Instagram 4:5 portrait size) with the hook, what it is, 3 highlights and who it's for, over a background illustrated by Workers AI (FLUX)
  - A Threads post in a conversational voice: a hook, 3 points and a question to invite replies. The post only goes to Telegram; it isn't saved in the repo or shown on the site, so nobody can see it before you post it
  - The voice comes from the `VOICE_PROMPT` secret, then a local `voice.local.md`, then the generic `templates/voice.md` (see [Your own voice](#your-own-voice))
  - Shown at the top of that day's report and on the home page, with the card ready to download
- Summaries are extracted from each README by rules (no paid AI):
  - **What**: the first introductory paragraph of the README (skipping badges, contribution notes and announcements)
  - **Used for**: categories (AI agents, web frontend, DevOps…) and project type, from topics, the description and README keywords
  - **Highlights**: the list under the README's Features / Highlights section
  - **Image**: the first non-badge image in the README, or GitHub's generated preview image
- The site comes in English and Traditional Chinese; switch in the top-right corner:
  - The English site (under `/en/`) shows the original README text
  - The Chinese site is translated with Cloudflare Workers AI, with the original text one click away
  - The home page remembers your choice; on first visit, non-Chinese browsers get the English site
- Listing history lives in `data/history.json`: 🆕 marks a repo's first appearance and 🔥 a streak. READMEs are refetched at most once every 7 days, and translations are cached
- Mobile friendly and installable as a PWA:
  - iPhone: Safari → Share → Add to Home Screen. Android / desktop Chrome: an "Install" button appears
  - The home page, the latest daily and weekly reports and any report you've opened work offline; the 80 most recent images are cached too

## Setup

Want your own copy? Fork this repo and follow the steps below. Your report will be published at `https://<your-user>.github.io/<repo-name>/`.

1. **GitHub Pages**: Settings → Pages → Source → **GitHub Actions**
2. **Cloudflare Workers AI translation** (Settings → Secrets and variables → Actions → New repository secret)
   - In the Cloudflare dashboard go to AI → Workers AI → **Use REST API**
   - `CLOUDFLARE_API_TOKEN`: click **Create a Workers AI API Token**
   - `CLOUDFLARE_ACCOUNT_ID`: the **Account ID** on the same page
   - The free plan includes 10,000 Neurons a day; translating one repo takes about 20
   - Then run the workflow once with `translate` to translate existing reports
3. **Telegram notifications** (also repo secrets)
   - `TELEGRAM_BOT_TOKEN`: message @BotFather on Telegram and create a bot with `/newbot`
   - `TELEGRAM_CHAT_ID`: send any message to your bot, then open
     `https://api.telegram.org/bot<TOKEN>/getUpdates`; it's the `message.chat.id` in the response
   - Without these the workflow still runs; it just doesn't send notifications
   - The daily pick is a second message: the card, plus the post in a block with a copy button
4. Go to Actions → Trending report → Run workflow to try it

GitHub Actions is free for public repos. A run takes 1–2 minutes.

## Environment variables

In GitHub Actions, the ones marked "Secret" go in the repo's secrets; the workflow already sets the rest. When running locally, set them as ordinary environment variables.

| Variable | What it's for | Default | If not set |
|---|---|---|---|
| `GITHUB_TOKEN` | Calls the GitHub API for repo details and READMEs. `GH_TOKEN` also works. Actions provides it automatically; locally use `$(gh auth token)` | — | Unauthenticated API calls are limited to 60 an hour, which one report can use up |
| `CLOUDFLARE_ACCOUNT_ID` | Secret. Your Cloudflare account ID, used to call Workers AI for translation | — | No translation; the Chinese site shows English |
| `CLOUDFLARE_API_TOKEN` | Secret. A Cloudflare API token with Workers AI permission | — | Same as above |
| `CLOUDFLARE_AI_MODEL` | The Workers AI model used for translation | `@cf/google/gemma-4-26b-a4b-it` | Uses the default model |
| `TELEGRAM_BOT_TOKEN` | Secret. Token of the Telegram bot that sends notifications, from @BotFather | — | No notification; the message is only printed to the log |
| `TELEGRAM_CHAT_ID` | Secret. The chat to notify (a person, group or channel) | — | Same as above |
| `PAGES_URL` | The site's public URL, used for report links in notifications and the language links in the pages. Actions sets it from the repo automatically | `https://ewanhohou.github.io/Github-Trending/` | Uses the default URL |
| `DAILY_LIMIT` | How many repos the daily report includes | `25` | Uses the default |
| `WEEKLY_LIMIT` | How many repos the weekly picks include | `10` | Uses the default |
| `NOTIFY_TOP` | How many top repos the Telegram message lists | `5` | Uses the default |
| `PICK_DEDUPE_DAYS` | A repo can't be the daily pick again within this many days | `90` | Uses the default |
| `CLOUDFLARE_IMAGE_MODEL` | The Workers AI model that draws the card background | `@cf/black-forest-labs/flux-1-schnell` | Uses the default model |
| `VOICE_PROMPT` | Secret, optional. Your own instructions for the voice of the Threads post, kept out of the public repo | — | Uses `voice.local.md` if it exists, otherwise `templates/voice.md` |

## Your own voice

`templates/voice.md` is a generic template. To give the post your own voice without publishing it:

1. Copy the template to `voice.local.md` in the repo root (it's in `.gitignore`) and edit it. Local runs use it automatically
2. Upload it as the `VOICE_PROMPT` secret so Actions uses it too:

   ```bash
   gh secret set VOICE_PROMPT < voice.local.md
   ```

3. After each edit, run the command again; the next run picks it up. To try it right away: Actions → Run workflow → `pick`

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
GITHUB_TOKEN=$(gh auth token) .venv/bin/python -m trending daily --no-notify
.venv/bin/python -m trending pick --no-notify   # the card is drawn with your installed Google Chrome
.venv/bin/python -m http.server 8790 --directory docs
```

| Command | What it does |
|---|---|
| `python -m trending daily [--no-notify]` | Builds today's report, rebuilds the site and sends the notification |
| `python -m trending weekly [--no-notify]` | Builds this week's picks |
| `python -m trending pick [--no-notify] [--redo] [--render-only]` | Picks today's standout repo and makes its card and post. `--redo` picks again, `--render-only` only redraws the card |
| `python -m trending render` | Rebuilds the site from `data/` only (after changing templates) |
| `python -m trending translate` | Translates existing reports and rebuilds the site |
| `python -m trending notify daily\|weekly\|pick` | Sends the notification for the latest report or pick |

## Project layout

```
trending/
  github.py     # parses the Trending page (falls back to the Search API) and calls the GitHub API
  summarize.py  # rule-based summaries, categories and image picking
  translate.py  # Cloudflare Workers AI translation
  report.py     # builds report JSON and keeps the listing history
  pick.py       # daily pick: choosing, card text, Threads post, AI background, card image
  i18n.py       # UI strings and category names for each language
  render.py     # writes the site to docs/ (Chinese at the root, English in docs/en/)
  notify.py     # Telegram notifications
templates/      # Jinja2 templates, CSS, the service worker (sw.js), app icons (static/),
                #   the card layout (card.html) and the post voice (voice.md)
data/           # report JSON, daily picks (picks/) and history (committed by Actions)
docs/           # the generated site
```

To add another language, add an entry to `LANGS`, `STRINGS` and `LABELS` in `trending/i18n.py`; its pages are written to `docs/<lang>/`.
