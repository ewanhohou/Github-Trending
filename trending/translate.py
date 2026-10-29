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

RULES = (
    "你是專業的軟體技術翻譯，把內容翻譯成台灣慣用的繁體中文；簡體中文請轉成繁體並改用台灣用語。"
    "保留產品名稱、專有名詞、程式碼、指令、repo 名稱與網址的原文。忠實翻譯，不要加入解釋，也不要增減內容。"
)
BATCH_PROMPT = RULES + (
    "使用者會給你多段以 [編號] 開頭的文字。請逐段翻譯，每段輸出一行，保留原本的 [編號] 開頭，"
    "例如「[1] 翻譯後的文字」。不要輸出其他任何文字。"
)
SINGLE_PROMPT = RULES + "只輸出翻譯結果，不要輸出其他任何文字。"

# 翻譯方式改了就調高版本號，舊的翻譯會在下次執行時重翻
VERSION = 2

# 連續幾個 repo 翻譯失敗就停止本次執行的翻譯，避免空轉浪費額度
MAX_CONSECUTIVE_FAILURES = 3

_session = requests.Session()
_failures = 0


def enabled() -> bool:
    return bool(config.CLOUDFLARE_ACCOUNT_ID and config.CLOUDFLARE_API_TOKEN) and _failures < MAX_CONSECUTIVE_FAILURES


def needs_translation(summary: dict, description: str) -> bool:
    return (not summary.get("translated") or summary.get("translation_version") != VERSION
            or summary.get("description_src") != description)


def _content(result) -> str:
    """Workers AI 不同模型的回應格式不同，統一取出文字內容。"""
    if isinstance(result, dict):
        if result.get("response") is not None:
            resp = result["response"]
            return resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
        choices = result.get("choices") or []
        if choices:
            return (choices[0].get("message") or {}).get("content") or ""
    return ""


def _parse_batch(text: str, expected: int) -> list[str] | None:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    found = {}
    for m in re.finditer(r"^\s*\[(\d+)\]\s*(.+?)\s*$", text, flags=re.M):
        found.setdefault(int(m.group(1)), m.group(2))
    if all(i in found for i in range(1, expected + 1)):
        return [found[i] for i in range(1, expected + 1)]
    # 模型偶爾仍會回 JSON 陣列
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            items = json.loads(text[start : end + 1])
        except ValueError:
            return None
        if isinstance(items, list) and len(items) == expected and all(isinstance(i, str) for i in items):
            return [i.strip() for i in items]
    return None


def run_model(model: str, payload: dict) -> dict | None:
    """呼叫一次 Workers AI 模型，回傳 result；設定錯誤、額度用完或連線失敗時回傳 None。"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"
    for attempt in range(2):
        try:
            resp = _session.post(url, json=payload, timeout=90,
                                 headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}"})
        except requests.RequestException as e:
            log.warning("workers ai request failed: %s", e)
        else:
            if resp.ok:
                return resp.json().get("result")
            log.warning("workers ai HTTP %s: %s", resp.status_code, resp.text[:200])
            if resp.status_code in (400, 401, 403):  # 重試也沒用
                return None
        time.sleep(3 * (attempt + 1))
    return None


def chat(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 2048) -> str | None:
    """用文字模型回答一次，回傳文字內容；失敗時回傳 None。"""
    payload = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        # 關閉思考模式：開著時思考會吃掉 max_tokens，導致回應空白或被截斷，而且很慢
        "chat_template_kwargs": {"enable_thinking": False},
    }
    result = run_model(config.CLOUDFLARE_AI_MODEL, payload)
    if result is None:
        return None
    return re.sub(r"<think>.*?</think>", "", _content(result), flags=re.S).strip()


def translate_many(texts: list[str]) -> list[str] | None:
    """翻譯多段文字，空字串原樣保留。先整批翻，格式對不上再逐段翻；仍失敗回傳 None。"""
    texts = [re.sub(r"\s+", " ", t).strip() for t in texts]
    pending = [i for i, t in enumerate(texts) if t]
    out = list(texts)
    if not pending:
        return out

    numbered = "\n".join(f"[{n}] {texts[i]}" for n, i in enumerate(pending, start=1))
    raw = chat(BATCH_PROMPT, numbered)
    result = _parse_batch(raw, len(pending)) if raw is not None else None
    if result is None:
        if raw is not None:
            log.warning("batch output not parseable, translating one by one: %r", raw[:300])
        result = []
        for i in pending:
            single = chat(SINGLE_PROMPT, texts[i])
            single = (single or "").strip()
            if not single:
                return None
            result.append(single)

    for i, translated in zip(pending, result):
        out[i] = translated
    return out


def translate_summary(summary: dict, description: str) -> None:
    """就地把 description / intro / features 的繁中版本寫進 summary。"""
    global _failures
    if not enabled():
        return
    features = summary.get("features", [])
    result = translate_many([description, summary.get("intro", ""), *features])
    if result is None:
        summary["translated"] = False
        _failures += 1
        if _failures >= MAX_CONSECUTIVE_FAILURES:
            log.error("translation failed %d times in a row, skipping the rest of this run", _failures)
        return
    _failures = 0
    summary["description_zh"] = result[0]
    summary["intro_zh"] = result[1]
    summary["features_zh"] = result[2:]
    summary["translated"] = True
    summary["translation_version"] = VERSION
    summary["description_src"] = description
