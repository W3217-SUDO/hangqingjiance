from __future__ import annotations

import os
import re
from decimal import Decimal
from functools import lru_cache

import httpx

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_RE = re.compile(r"[A-Za-z]")
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<currency>[$€£])?\s*"
    r"(?P<number>\d+(?:,\d{3})*(?:\.\d+)?)"
    r"(?:\s*(?P<scale>trillion|billion|million|thousand|万亿|亿|万|[TBMK]))?"
    r"(?P<percent>%)?(?![A-Za-z0-9])",
    re.IGNORECASE,
)
SCALES = {
    "trillion": Decimal("1000000000000"),
    "t": Decimal("1000000000000"),
    "billion": Decimal("1000000000"),
    "b": Decimal("1000000000"),
    "million": Decimal("1000000"),
    "m": Decimal("1000000"),
    "thousand": Decimal("1000"),
    "k": Decimal("1000"),
    "万亿": Decimal("1000000000000"),
    "亿": Decimal("100000000"),
    "万": Decimal("10000"),
}
SYSTEM_PROMPT = (
    "你是财经新闻标题翻译员。只输出一行简体中文译文，不解释、不补充事实。"
    "数字、金额、百分比和量级必须与原文一致，准确区分上涨和下跌、流入和流出。"
    "Fed 译为美联储，ETF 等证券代码保持原样。"
)


class TranslationUnavailable(RuntimeError):
    pass


def contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def needs_chinese_translation(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned or contains_cjk(cleaned):
        return False
    return bool(LATIN_RE.search(cleaned))


def _numeric_values(text: str) -> list[tuple[Decimal, bool]]:
    values = []
    for match in NUMBER_RE.finditer(text):
        value = Decimal(match.group("number").replace(",", ""))
        scale = match.group("scale")
        if scale:
            value *= SCALES[scale.lower()]
        values.append((value, bool(match.group("percent"))))
    return values


def validate_numeric_facts(source: str, translated: str) -> None:
    actual = _numeric_values(translated)
    for match in NUMBER_RE.finditer(source):
        raw = match.group("number").replace(",", "")
        if not (match.group("scale") or match.group("percent") or match.group("currency") or len(raw) >= 3):
            continue
        value = Decimal(raw)
        if match.group("scale"):
            value *= SCALES[match.group("scale").lower()]
        if (value, bool(match.group("percent"))) not in actual:
            raise TranslationUnavailable(f"译文数字与原文不一致: {match.group(0).strip()}")


@lru_cache(maxsize=4096)
def translate_text_to_chinese(text: str) -> str:
    cleaned = (text or "").strip()
    if not needs_chinese_translation(cleaned):
        return cleaned

    endpoint = os.getenv("MARKET_STREAM_TRANSLATION_ENDPOINT", "http://127.0.0.1:8012/v1/chat/completions")
    model = os.getenv("MARKET_STREAM_TRANSLATION_MODEL", "qwen3-4b-translation")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": cleaned},
        ],
        "temperature": 0,
        "max_tokens": 256,
        "stream": False,
    }
    try:
        response = httpx.post(endpoint, json=payload, timeout=25)
        response.raise_for_status()
        translated = response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise TranslationUnavailable("本机翻译服务调用失败") from exc

    if not translated or not contains_cjk(translated):
        raise TranslationUnavailable("翻译服务未返回有效中文")
    validate_numeric_facts(cleaned, translated)
    return translated
