# GitHub Trending 報告

每天掃描 [GitHub Trending](https://github.com/trending)，整理每個熱門 repo「是什麼、用在哪、有什麼亮點」並附上圖片，產生網頁報告發佈到 GitHub Pages，再用 Telegram 通知。

- 每日報告：台北時間 08:30，全語言 Top 25
- 每週精選：每週日 09:00，週榜 Top 10，加上本週最常上每日榜的 repo
- 摘要用規則從 README 擷取，再用 Cloudflare Workers AI 翻成繁體中文：
  - **是什麼**：README 的第一段介紹（會略過 badge、貢獻說明、公告等段落）
  - **用在哪**：依 topics、描述、README 的關鍵字判斷分類（AI Agent、Web 前端、DevOps…）與專案類型
  - **亮點功能**：README 中 Features／Highlights 段落的清單
  - **圖片**：README 中第一張非 badge 的圖片；沒有就用 GitHub 自動產生的預覽圖
- 翻譯只做忠實翻譯，不改寫內容；英文原文收在每張卡片的「英文原文」裡。沒設定 Cloudflare 時顯示英文
- 上榜歷史記錄在 `data/history.json`：標示 🆕 首次上榜、🔥 連續上榜天數；同一個 repo 7 天內不重抓 README，翻譯也會快取
- 支援手機閱讀與 PWA：可以「加入主畫面」當 App 開啟（iPhone 用 Safari 分享 → 加入主畫面；Android／桌面 Chrome 會出現「安裝」按鈕）。
  首頁、最新一期日報週報與看過的報告可以離線閱讀，圖片也會快取最近 80 張

## 設定

1. **GitHub Pages**：Settings → Pages → Source 選 **GitHub Actions**
2. **Cloudflare Workers AI 翻譯**（同樣放在 repo Secrets）
   - 到 Cloudflare dashboard → AI → Workers AI → **Use REST API**
   - `CLOUDFLARE_API_TOKEN`：選 **Create a Workers AI API Token** 建立
   - `CLOUDFLARE_ACCOUNT_ID`：同一頁的 **Account ID**
   - 免費方案每天 10,000 Neurons，每個 repo 翻譯約用 20 Neurons
   - 設定好之後到 Actions 用 `translate` 跑一次，可以替既有報告補上中文
3. **Telegram 通知**（Settings → Secrets and variables → Actions → New repository secret）
   - `TELEGRAM_BOT_TOKEN`：在 Telegram 找 @BotFather，用 `/newbot` 建立 bot 後取得
   - `TELEGRAM_CHAT_ID`：先傳任意訊息給你的 bot，再開啟
     `https://api.telegram.org/bot<TOKEN>/getUpdates`，回應裡的 `message.chat.id` 就是
   - 沒設定的話流程照常跑，只是不發通知
4. 到 Actions → Trending report → Run workflow 手動跑一次確認

Public repo 使用 GitHub Actions 不計費，每次執行約 1 分鐘。

## 本機執行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
GITHUB_TOKEN=$(gh auth token) .venv/bin/python -m trending daily --no-notify
.venv/bin/python -m http.server 8790 --directory docs
```

| 指令 | 說明 |
|---|---|
| `python -m trending daily [--no-notify]` | 產生今日報告、重建網頁、發通知 |
| `python -m trending weekly [--no-notify]` | 產生本週精選 |
| `python -m trending render` | 只依 `data/` 重建網頁（改模板後用） |
| `python -m trending translate` | 替既有報告補上中文翻譯並重建網頁 |
| `python -m trending notify daily\|weekly` | 傳送最新一份報告的通知 |

可用環境變數調整：`DAILY_LIMIT`、`WEEKLY_LIMIT`、`NOTIFY_TOP`、`PAGES_URL`、`CLOUDFLARE_AI_MODEL`（預設 `@cf/google/gemma-4-26b-a4b-it`）。

## 結構

```
trending/
  github.py     # 解析 Trending 頁面（失敗時改用 Search API）、呼叫 GitHub API
  summarize.py  # 規則式摘要、分類、選圖
  translate.py  # Cloudflare Workers AI 翻譯
  report.py     # 產生報告 JSON、維護上榜歷史
  render.py     # 輸出 docs/ 網頁
  notify.py     # Telegram 通知
templates/      # Jinja2 模板、CSS、service worker（sw.js）與 App 圖示（static/）
data/           # 報告 JSON 與歷史（由 Actions 自動 commit）
docs/           # 產生的網頁
```
