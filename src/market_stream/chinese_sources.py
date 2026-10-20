"""NewsNow source adapters ported to Python, modified 2026-10-20.
Upstream: newsnext/newsnow @ 0560c993b226cd2fd07d8a79875d50551f52c584
server/sources/{jin10,wallstreetcn,mktnews}.ts — MIT, copyright 2024 ourongxing.
See third_party/newsnow-LICENSE. Only public, unlocked text is ingested.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from .config import Source
from .models import StreamItem


def parse_json_source(source: Source, raw: str) -> list[StreamItem]:
    from .fetcher import clean_text, match_terms
    if source.parser == "jin10":
        payload = json.loads(re.sub(r";\s*$", "", re.sub(r"^\s*var\s+newest\s*=\s*", "", raw)))
    else:
        payload = json.loads(raw)
    rows = payload if source.parser == "jin10" else payload.get("data", {}).get("items", []) if source.parser == "wallstreetcn" else payload.get("data", [])
    items = []
    for row in rows[:60]:
        data = row.get("data") or {}
        if data.get("lock") or data.get("vip_level") or row.get("channel") and 5 in row["channel"]:
            continue
        if source.parser == "wallstreetcn":
            title = clean_text(row.get("title") or row.get("content_text"))
            url = row.get("uri", "")
            published = datetime.fromtimestamp(float(row.get("display_time", 0)), timezone.utc)
        else:
            title = clean_text(data.get("title") or data.get("content"))
            if source.parser == "jin10":
                url = f'https://flash.jin10.com/detail/{row["id"]}'
                published = datetime.strptime(row["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
            else:
                url = f'https://mktnews.net/flashDetail.html?id={row["id"]}'
                published = datetime.fromisoformat(row["time"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if not title or urlparse(url).scheme not in {"https", "http"}:
            continue
        if len(title) > 400:
            title = title[:400] + "…"
        terms = match_terms(title, "")
        if row.get("important"):
            terms.append("source_important")
        items.append(StreamItem(source.name, source.category, source.region, title, "", url, source.homepage, published, matched_terms=terms, title_zh=title if re.search(r"[\u3400-\u9fff]", title) else ""))
    return items
