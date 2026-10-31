"""確保中文輸出是繁體：模型偶爾會混進簡體字。"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import opencc

# 以空白和標點切成片段，只轉換含簡體專用字的片段
_SEGMENT = re.compile(r"[^\s，。、；：！？「」『』（）《》【】,.;:!?()\[\]|/]+")


@lru_cache(maxsize=1)
def _simplified_only() -> frozenset[str]:
    """簡體專用字，例如「这」「网」。「台」「了」「家」這種繁體也會用的字不算，
    台灣標準字形（像「群」，字典的繁體寫法是「羣」）也不算。"""
    folder = Path(opencc.__file__).parent / "dictionary"
    tw = dict(_entries(folder / "TWVariants.txt"))
    chars = set()
    for key, values in _entries(folder / "STCharacters.txt"):
        if key not in values and key not in {tw.get(v, [v])[0] for v in values}:
            chars.add(key)
    return frozenset(chars)


def _entries(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, values = line.partition("\t")
        if key:
            yield key, values.split()


@lru_cache(maxsize=1)
def _converter() -> opencc.OpenCC:
    return opencc.OpenCC("s2twp")


def to_traditional(text: str) -> str:
    """把簡體片段轉成繁體與台灣用語。已經是繁體的片段不動，避免把「工作台」「了解」改成「工作臺」「瞭解」。"""
    if not text:
        return text
    simplified = _simplified_only()
    if not any(ch in simplified for ch in text):
        return text

    def convert(m: re.Match) -> str:
        part = m.group()
        return _converter().convert(part) if any(ch in simplified for ch in part) else part

    return _SEGMENT.sub(convert, text)
