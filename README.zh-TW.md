# GitHub Trending 報告

[English](README.md) | **繁體中文**

[![線上報告](https://img.shields.io/badge/%E7%B7%9A%E4%B8%8A%E5%A0%B1%E5%91%8A-ewanhohou.github.io-2ea44f?logo=github)](https://ewanhohou.github.io/Github-Trending/)
[![Trending report](https://github.com/ewanhohou/Github-Trending/actions/workflows/report.yml/badge.svg)](https://github.com/ewanhohou/Github-Trending/actions/workflows/report.yml)

**👉 每天看今天的熱門 repo：<https://ewanhohou.github.io/Github-Trending/>**

| | 繁體中文 | English |
|---|---|---|
| 首頁 | [所有報告](https://ewanhohou.github.io/Github-Trending/) | [All reports](https://ewanhohou.github.io/Github-Trending/en/) |
| 最新日報 | [daily/latest](https://ewanhohou.github.io/Github-Trending/daily/latest.html) | [en/daily/latest](https://ewanhohou.github.io/Github-Trending/en/daily/latest.html) |
| 最新週報 | [weekly/latest](https://ewanhohou.github.io/Github-Trending/weekly/latest.html) | [en/weekly/latest](https://ewanhohou.github.io/Github-Trending/en/weekly/latest.html) |

每天掃描 [GitHub Trending](https://github.com/trending)，整理每個熱門 repo「是什麼、用在哪、有什麼亮點」並附上圖片，產生網頁報告發佈到 GitHub Pages，再用 Telegram 通知。手機上可以「加入主畫面」當 App 使用。

## 功能

- 每日報告：台北時間 08:30，全語言 Top 25
- 每週精選：每週日 09:00，週榜 Top 10，加上本週最常上每日榜的 repo
- 每日精選：每天挑一個最值得推薦的 repo，90 天內不重複，做成可以直接發 Threads 的圖文送到 Telegram
  - 先用規則取前 5 名（今日星數、AI 相關、首次上榜、新專案加分，清單與教學類扣分），再讓 Workers AI 挑一個並寫推薦理由
  - 1080×1350 深色說明圖（Threads／IG 直式 4:5）：鉤子、是什麼、3 個重點、適合誰，背景由 Workers AI（FLUX）生成，生成後再請 Gemma 看一次，畫出文字就重畫（最多 3 次，仍有字就改用漸層背景）。圖上不放日期，哪天忘了發，改天還能用
  - Threads 貼文用聊天口吻：開頭鉤子、3 個重點、結尾提問引導留言。貼文只送到 Telegram，不存進 repo、也不放上網站，你發文前別人看不到
  - Telegram：日報那則最後附上精選的 repo 和推薦理由；精選是說明圖加一則留言。圖說是完整貼文，最後一行接上幾個跟這個專案有關的標籤（總長不超過 Threads 的 500 字）；留言那則是「🔗 留言區連結」。兩則都按「複製」就能直接貼
  - 設定好 [發到 Threads](#發到-threads選用) 之後，說明圖下面會有「🚀 發到 Threads」按鈕：看過貼文覺得可以再按，就會發到預設的頻道並把連結貼在第一則回覆，也可以先按「🏷 換頻道」選別的頻道
  - 口吻依序用 `VOICE_PROMPT` Secret、本機的 `voice.local.md`、通用範本 `templates/voice.md`（見[設定自己的口吻](#設定自己的口吻)）
  - 當天日報最上方與首頁都會顯示，說明圖可以直接下載
- 摘要用規則從 README 擷取，再用 Cloudflare Workers AI 翻成繁體中文。AI 產生的文字都會再檢查一次，混進來的簡體字會轉成繁體與台灣用語：
  - **是什麼**：README 的第一段介紹（會略過 badge、貢獻說明、公告等段落）
  - **用在哪**：依 topics、描述、README 的關鍵字判斷分類（AI Agent、Web 前端、DevOps…）與專案類型
  - **亮點功能**：README 中 Features／Highlights 段落的清單
  - **圖片**：README 中第一張非 badge 的圖片；沒有就用 GitHub 自動產生的預覽圖
- 網頁有繁體中文與英文兩種版本，右上角可以切換：
  - 中文版顯示翻譯，英文原文收在每張卡片的「英文原文」裡；沒設定 Cloudflare 時顯示英文
  - 英文版顯示 README 原文，放在 `/en/` 底下
  - 首頁會記住你選的語言；沒選過的話，瀏覽器不是中文就會開英文版
- 上榜歷史記錄在 `data/history.json`：標示 🆕 首次上榜、🔥 連續上榜天數；同一個 repo 7 天內不重抓 README，翻譯也會快取
- 支援手機閱讀與 PWA：
  - iPhone 用 Safari 分享 → 加入主畫面；Android／桌面 Chrome 會出現「安裝」按鈕
  - 首頁、最新一期日報週報與看過的報告可以離線閱讀，圖片也會快取最近 80 張

## 設定

想自己架一份？Fork 這個 repo 後照下面設定，報告會發佈到 `https://<你的帳號>.github.io/<repo 名稱>/`。

1. **GitHub Pages**：Settings → Pages → Source 選 **GitHub Actions**
2. **Cloudflare Workers AI 翻譯**（Settings → Secrets and variables → Actions → New repository secret）
   - 到 Cloudflare dashboard → AI → Workers AI → **Use REST API**
   - `CLOUDFLARE_API_TOKEN`：選 **Create a Workers AI API Token** 建立
   - `CLOUDFLARE_ACCOUNT_ID`：同一頁的 **Account ID**
   - 免費方案每天 10,000 Neurons，每個 repo 翻譯約用 20 Neurons
   - 設定好之後到 Actions 用 `translate` 跑一次，可以替既有報告補上中文
3. **Telegram 通知**（同樣放在 repo Secrets）
   - `TELEGRAM_BOT_TOKEN`：在 Telegram 找 @BotFather，用 `/newbot` 建立 bot 後取得
   - `TELEGRAM_CHAT_ID`：先傳任意訊息給你的 bot，再開啟
     `https://api.telegram.org/bot<TOKEN>/getUpdates`，回應裡的 `message.chat.id` 就是
   - 沒設定的話流程照常跑，只是不發通知
   - 每日精選是第二則訊息：說明圖加上貼文，貼文放在有「複製」按鈕的區塊裡
   - 設定 [發到 Threads](#發到-threads選用) 之後 bot 會改用 webhook，`getUpdates` 就查不到訊息了，chat id 要先查好
4. 到 Actions → Trending report → Run workflow 手動跑一次確認

Public repo 使用 GitHub Actions 不計費，每次執行約 1～2 分鐘。

## 發到 Threads（選用）

`worker/` 是一個 Cloudflare Worker（免費方案就夠）：在 Telegram 按「🚀 發到 Threads」後，它用 Threads API 發出說明圖和貼文，再把「🔗 留言區連結」貼成第一則回覆，完成後按鈕會變成貼文的連結。發文失敗會在 Telegram 說原因，修好可以再按一次，不會重複發文。

1. 到 [Meta for Developers](https://developers.facebook.com/apps/) 建立 app，用途選 **Access the Threads API**
2. 用途的設定裡：
   - 權限加上 `threads_basic`、`threads_content_publish` 和 `threads_manage_replies`（貼留言區連結要用）
   - 三個 callback URL（Redirect、Uninstall、Delete）都填 `https://github-trending-threads.<你的子網域>.workers.dev/auth/callback`
   - 記下 **Threads app ID** 和 **Threads app secret**
3. App roles → Roles → Add People → **Threads Tester**，加入要發文的 Threads 帳號；再用那個帳號到 Threads 網站 → 設定 → 帳號 → 網站權限 接受邀請。開發中的 app 只有測試人員能授權，不需要送審
4. 把 app ID 和 secret 存進 repo Secrets（在終端機輸入，不會留在畫面上）：

   ```bash
   gh secret set THREADS_APP_ID
   gh secret set THREADS_APP_SECRET
   ```

5. 部署用的 Cloudflare token 要有 Workers 權限。翻譯用的那把沒有的話，用 **Edit Cloudflare Workers** 範本另外建一把，存成 `CLOUDFLARE_WORKERS_TOKEN`
6. Actions → **Deploy Threads worker** → Run workflow。之後 `worker/` 有改動會自動部署
7. 打開 `https://github-trending-threads.<你的子網域>.workers.dev/auth`，用 Threads 帳號登入並允許。這一步也會設定 Telegram webhook
8. 打開按鈕：

   ```bash
   gh variable set THREADS_PUBLISH --body 1
   ```

Threads 的 token 60 天到期，Worker 每天自動更新一次；更新失敗會在 Telegram 通知，重新打開 `/auth` 授權就好。按鈕預設發到 `AI Threads` 頻道（主題標籤），按「🏷 換頻道」可以改發到別的頻道或不加頻道。頻道清單在 `worker/topics.json`，第一個是預設，改完 push 就會重新部署。頻道名稱最多 50 字，不能有 `.` 和 `&`。

## 環境變數

在 GitHub Actions 裡，標示「Secret」的要放在 repo Secrets，其他的 workflow 已經設好。本機執行時用一般的環境變數設定。

| 變數 | 用途 | 預設值 | 沒設定時 |
|---|---|---|---|
| `GITHUB_TOKEN` | 呼叫 GitHub API 取得 repo 資訊與 README。也可以用 `GH_TOKEN`。Actions 會自動提供；本機可用 `$(gh auth token)` | — | 未登入的 API 每小時只有 60 次，一份報告就可能用完 |
| `CLOUDFLARE_ACCOUNT_ID` | Secret。Cloudflare 帳號 ID，用來呼叫 Workers AI 翻譯 | — | 不翻譯，中文版也顯示英文 |
| `CLOUDFLARE_API_TOKEN` | Secret。有 Workers AI 權限的 Cloudflare API token | — | 同上 |
| `CLOUDFLARE_AI_MODEL` | 翻譯用的 Workers AI 模型 | `@cf/google/gemma-4-26b-a4b-it` | 用預設模型 |
| `TELEGRAM_BOT_TOKEN` | Secret。發送通知的 Telegram bot token，向 @BotFather 取得 | — | 不發通知，只把訊息印在 log |
| `TELEGRAM_CHAT_ID` | Secret。通知要送到的聊天室 ID（個人、群組或頻道） | — | 同上 |
| `PAGES_URL` | 網站的公開網址，用在通知裡的報告連結與網頁的語言對照連結。Actions 會依 repo 自動設定 | `https://ewanhohou.github.io/Github-Trending/` | 用預設網址 |
| `DAILY_LIMIT` | 每日報告收錄幾個 repo | `25` | 用預設值 |
| `WEEKLY_LIMIT` | 每週精選收錄幾個 repo | `10` | 用預設值 |
| `NOTIFY_TOP` | Telegram 通知列出前幾名 | `5` | 用預設值 |
| `PICK_DEDUPE_DAYS` | 每日精選幾天內不重複 | `90` | 用預設值 |
| `CLOUDFLARE_IMAGE_MODEL` | 產生說明圖背景的 Workers AI 模型 | `@cf/black-forest-labs/flux-1-schnell` | 用預設模型 |
| `THREADS_PUBLISH` | Repo 變數（Variables），選填。設成 `1` 時精選的說明圖下面會有「發到 Threads」按鈕，見[發到 Threads](#發到-threads選用) | — | 沒有按鈕 |
| `VOICE_PROMPT` | Secret，選填。你自己的 Threads 貼文口吻說明，不會出現在公開的 repo | — | 有 `voice.local.md` 就用它，否則用 `templates/voice.md` |

## 設定自己的口吻

`templates/voice.md` 是通用範本。想用自己的口吻又不公開：

1. 把範本複製成 repo 根目錄的 `voice.local.md`（已列在 `.gitignore`）再修改，本機執行會自動使用
2. 上傳成 `VOICE_PROMPT` Secret，讓 Actions 也用它：

   ```bash
   gh secret set VOICE_PROMPT < voice.local.md
   ```

3. 之後每次修改再執行一次上面的指令，下一次執行就會套用。想馬上試：Actions → Run workflow → 選 `pick`

## 本機執行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
GITHUB_TOKEN=$(gh auth token) .venv/bin/python -m trending daily --no-notify
.venv/bin/python -m trending pick --no-notify   # 說明圖用本機安裝的 Google Chrome 截圖
.venv/bin/python -m http.server 8790 --directory docs
```

| 指令 | 說明 |
|---|---|
| `python -m trending daily [--no-notify]` | 產生今日報告、重建網頁、發通知 |
| `python -m trending weekly [--no-notify]` | 產生本週精選 |
| `python -m trending pick [--no-notify] [--redo] [--render-only] [--repost]` | 挑今天的每日精選並產生說明圖與貼文。`--redo` 重新挑選，`--render-only` 只重畫說明圖，`--repost` 只重寫貼文與標籤（Actions 手動跑 `repost` 會重送到 Telegram） |
| `python -m trending render` | 只依 `data/` 重建網頁（改模板後用） |
| `python -m trending translate` | 替既有報告補上中文翻譯並重建網頁 |
| `python -m trending notify daily\|weekly\|pick` | 傳送最新一份報告或每日精選的通知 |

## 結構

```
trending/
  github.py     # 解析 Trending 頁面（失敗時改用 Search API）、呼叫 GitHub API
  summarize.py  # 規則式摘要、分類、選圖
  translate.py  # Cloudflare Workers AI 翻譯
  zh.py         # 把混進來的簡體字轉成繁體
  report.py     # 產生報告 JSON、維護上榜歷史
  pick.py       # 每日精選：挑選、說明圖文案、Threads 貼文、AI 背景圖、說明圖
  i18n.py       # 網頁介面文字與分類名稱的中英對照
  render.py     # 輸出 docs/ 網頁（中文在根目錄，英文在 docs/en/）
  notify.py     # Telegram 通知
worker/         # Cloudflare Worker：按下 Telegram 按鈕後發到 Threads
templates/      # Jinja2 模板、CSS、service worker（sw.js）、App 圖示（static/）、
                #   說明圖版面（card.html）與貼文口吻（voice.md）
data/           # 報告 JSON、每日精選（picks/）與歷史（由 Actions 自動 commit）
docs/           # 產生的網頁
```

要加其他語言：在 `trending/i18n.py` 的 `LANGS`、`STRINGS`、`LABELS` 各加一組，網頁會輸出到 `docs/<語言>/`。
