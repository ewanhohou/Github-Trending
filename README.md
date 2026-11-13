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
  - A 1080×1350 dark card (the Threads / Instagram 4:5 portrait size) with the hook, what it is, 3 highlights and who it's for, over a background illustrated by Workers AI (FLUX). Gemma looks at each background and it is redrawn if it contains text (up to 3 tries, then a plain gradient). The card has no date, so if you miss a day you can still post it later
  - A Threads post in a conversational voice: a hook, 3 points and a question to invite replies. The post only goes to Telegram; it isn't saved in the repo or shown on the site, so nobody can see it before you post it
  - Telegram: the daily report ends with the pick and why it was picked; the pick comes as the card plus a comment. The card's caption is the full post, with a few topic tags for this repo added to its last line (kept within Threads' 500-character limit); the next message is the "🔗 留言區連結" line for the first comment. Copy either one and paste it straight into Threads
  - Once [posting to Threads](#posting-to-threads-optional) is set up, the card gets a "🚀 發到 Threads" button: read the post, tap it, and it is posted to the default topic with the link as the first reply; tap "🏷 換頻道" first to pick another topic
  - The voice comes from the `VOICE_PROMPT` secret, then a local `voice.local.md`, then the generic `templates/voice.md` (see [Your own voice](#your-own-voice))
  - Shown at the top of that day's report and on the home page, with the card ready to download
- Summaries are extracted from each README by rules (no paid AI):
  - **What**: the first introductory paragraph of the README (skipping badges, contribution notes and announcements)
  - **Used for**: categories (AI agents, web frontend, DevOps…) and project type, from topics, the description and README keywords
  - **Highlights**: the list under the README's Features / Highlights section
  - **Image**: the first non-badge image in the README, or GitHub's generated preview image
- The site comes in English and Traditional Chinese; switch in the top-right corner:
  - The English site (under `/en/`) shows the original README text
  - The Chinese site is translated with Cloudflare Workers AI, with the original text one click away. All AI-written text is checked again, and any stray Simplified Chinese is converted to Traditional with Taiwan wording
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
   - After [posting to Threads](#posting-to-threads-optional) is set up the bot uses a webhook, so `getUpdates` no longer shows messages; look up the chat id first
4. Go to Actions → Trending report → Run workflow to try it

GitHub Actions is free for public repos. A run takes 1–2 minutes.

## Posting to Threads (optional)

`worker/` is a Cloudflare Worker (the free plan is enough). When you tap "🚀 發到 Threads" in Telegram, it posts the card and the post through the Threads API, then adds the "🔗 留言區連結" line as the first reply, and the button turns into a link to the post. If posting fails, Telegram tells you why; fix it and tap again, and nothing is posted twice.

1. Create an app at [Meta for Developers](https://developers.facebook.com/apps/) with the **Access the Threads API** use case
2. In the use case settings:
   - Add the `threads_basic`, `threads_content_publish` and `threads_manage_replies` permissions (the last one is for the comment-link reply)
   - Set all three callback URLs (redirect, uninstall, delete) to `https://github-trending-threads.<your-subdomain>.workers.dev/auth/callback`
   - Note the **Threads app ID** and **Threads app secret**
3. App roles → Roles → Add People → **Threads Tester** and add the Threads account you post from; then, signed in as that account, accept the invite on the Threads website under Settings → Account → Website permissions. An app in development can only be authorized by its testers, so no app review is needed
4. Save the app ID and secret as repo secrets (typed into the terminal, not left on screen):

   ```bash
   gh secret set THREADS_APP_ID
   gh secret set THREADS_APP_SECRET
   ```

5. Deploying needs a Cloudflare token with Workers permissions. If the translation token doesn't have them, create one from the **Edit Cloudflare Workers** template and save it as `CLOUDFLARE_WORKERS_TOKEN`
6. Actions → **Deploy Threads worker** → Run workflow. Later changes under `worker/` deploy automatically
7. Open `https://github-trending-threads.<your-subdomain>.workers.dev/auth`, sign in with the Threads account and allow it. This also sets up the Telegram webhook
8. Turn the button on:

   ```bash
   gh variable set THREADS_PUBLISH --body 1
   ```

Threads tokens expire after 60 days; the Worker refreshes it once a day and tells you on Telegram if that fails, in which case open `/auth` again. The button posts to the `AI Threads` topic by default; tap "🏷 換頻道" to post under another topic or none. The topics are listed in `worker/topics.json`, the first being the default; push a change and the Worker redeploys. A topic is at most 50 characters and can't contain `.` or `&`.

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
| `THREADS_PUBLISH` | Repo variable, optional. Set to `1` to add the "post to Threads" button under the pick's card; see [Posting to Threads](#posting-to-threads-optional) | — | No button |
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
| `python -m trending pick [--no-notify] [--redo] [--render-only] [--repost]` | Picks today's standout repo and makes its card and post. `--redo` picks again, `--render-only` only redraws the card, `--repost` only rewrites the post and tags (running `repost` from Actions sends it to Telegram again) |
| `python -m trending render` | Rebuilds the site from `data/` only (after changing templates) |
| `python -m trending translate` | Translates existing reports and rebuilds the site |
| `python -m trending notify daily\|weekly\|pick` | Sends the notification for the latest report or pick |

## Project layout

```
trending/
  github.py     # parses the Trending page (falls back to the Search API) and calls the GitHub API
  summarize.py  # rule-based summaries, categories and image picking
  translate.py  # Cloudflare Workers AI translation
  zh.py         # converts stray Simplified Chinese to Traditional
  report.py     # builds report JSON and keeps the listing history
  pick.py       # daily pick: choosing, card text, Threads post, AI background, card image
  i18n.py       # UI strings and category names for each language
  render.py     # writes the site to docs/ (Chinese at the root, English in docs/en/)
  notify.py     # Telegram notifications
worker/         # Cloudflare Worker: posts to Threads when the Telegram button is tapped
templates/      # Jinja2 templates, CSS, the service worker (sw.js), app icons (static/),
                #   the card layout (card.html) and the post voice (voice.md)
data/           # report JSON, daily picks (picks/) and history (committed by Actions)
docs/           # the generated site
```

To add another language, add an entry to `LANGS`, `STRINGS` and `LABELS` in `trending/i18n.py`; its pages are written to `docs/<lang>/`.
