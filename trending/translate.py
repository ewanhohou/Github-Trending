"""用 Cloudflare Workers AI 把摘要翻成繁體中文（台灣用語）。
沒設定 CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN 時略過，頁面會顯示英文原文。"""
from __future__ import annotations

import json
import logging
import re
import time

import requests

from . import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是專業的軟體技術翻譯。使用者會給你一個 JSON 字串陣列，請把每個字串翻譯成台灣慣用的繁體中文；"
    "簡體中文請轉成繁體並改用台灣用語。保留產品名稱、專有名詞、程式碼、指令、repo 名稱與網址的原文。"
    "忠實翻譯，不要加入解釋，也不要增減內容。"
    "只輸出一個與輸入等長、順序相同的 JSON 字串陣列，不要輸出其他任何文字。"
)

_session = requests.Session()


def enabled() -> bool:
    return bool(config.CLOUDFLARE_ACCOUNT_ID and config.CLOUDFLARE_API_TOKEN)


def _content(result) -> str:
    """Workers AI 不同模型的回應格式不同，統一取出文字內容。"""
    if isinstance(result, dict):
        if "response" in result:
            resp = result["response"]
            return resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
        choices = result.get("choices") or []
        if choices:
            return choices[0].get("message", {}).get("content") or ""
    return ""


def _parse(text: str, expected: int) -> list[str] | None:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        items = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(items, list) or len(items) != expected or not all(isinstance(i, str) for i in items):
        return None
    return [i.strip() for i in items]


def _run(texts: list[str]) -> list[str] | None:
    url = (f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}"
           f"/ai/run/{config.CLOUDFLARE_AI_MODEL}")
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
        ],
        "max_tokens": 2048,
        "temperature": 0.2,
    }
    for attempt in range(3):
        try:
            resp = _session.post(url, json=payload, timeout=60,
                                 headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}"})
        except requests.RequestException as e:
            log.warning("workers ai request failed: %s", e)
        else:
            if resp.ok:
                parsed = _parse(_content(resp.json().get("result")), len(texts))
                if parsed is not None:
                    return parsed
                log.warning("workers ai returned unexpected output")
            else:
                log.warning("workers ai HTTP %s: %s", resp.status_code, resp.text[:200])
                if resp.status_code in (400, 401, 403):  # 設定錯誤或額度用完，重試也沒用
                    return None
        time.sleep(3 * (attempt + 1))
    return None


def translate_many(texts: list[str]) -> list[str] | None:
    """翻譯多段文字，空字串原樣保留。失敗回傳 None。"""
    texts = [re.sub(r"\s+", " ", t).strip() for t in texts]
    pending = [i for i, t in enumerate(texts) if t]
    out = list(texts)
    if not pending:
        return out
    result = _run([texts[i] for i in pending])
    if result is None:
        return None
    for i, translated in zip(pending, result):
        out[i] = translated
    return out


def translate_summary(summary: dict, description: str) -> None:
    """就地把 description / intro / features 的繁中版本寫進 summary。"""
    if not enabled():
        return
    features = summary.get("features", [])
    result = translate_many([description, summary.get("intro", ""), *features])
    if result is None:
        summary["translated"] = False
        return
    summary["description_zh"] = result[0]
    summary["intro_zh"] = result[1]
    summary["features_zh"] = result[2:]
    summary["translated"] = True
    summary["description_src"] = description
