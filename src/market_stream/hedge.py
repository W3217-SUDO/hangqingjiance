"""Crossmarket Pulse extension, added 2026-10-20. Uses the upstream pipeline/store/SSE."""
from __future__ import annotations
import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from .config import SOURCES, ACTIVE_SOURCE_NAMES
from .fetcher import SOURCE_HEALTH
from .relevance import analyze, select_assets
from .translation import translate_text_to_chinese, contains_cjk

ASSETS = ["US30", "US500", "BTC", "ETH", "XBR", "XTI"]
STATIC = Path(__file__).parent / "static"
TRANSLATIONS = asyncio.Semaphore(3)


def relevant(item):
    return item.source_name in ACTIVE_SOURCE_NAMES and bool(select_assets(analyze(item.title, item.source_name), "related"))


def event_key(item):
    title = item["title_original"].lower()
    # Group repeated release/ticker headlines only in the compact brief; keep the full tape.
    for key, pattern in [
        ("adp", r"(?<![a-z])adp(?![a-z])"), ("nfp", r"nonfarm|non-farm|非农"),
        ("cpi", r"\bcpi\b|消费者价格指数"), ("catl", r"\bcatl\b|宁德时代"),
        ("apple", r"\b(apple|aapl)\b|苹果"), ("gm", r"\b(gm|general motors)\b|通用汽车"),
        ("oil-price", r"(?:wti|brent|原油|布伦特).*(?:\$|涨幅|跌幅|美元/桶|intraday|surges|rose|gained)"),
    ]:
        if re.search(pattern, title): return key
    return item["id"]


def decorate(item, mode="strict", asset="all"):
    d = item.as_dict("en")
    analysis = analyze(item.title, item.source_name)
    assets = select_assets(analysis, mode, asset)
    lead = max(assets, key=lambda a:analysis["asset_scores"][a], default=None)
    source = next((s for s in SOURCES if s.name == item.source_name), None)
    official = urlparse(item.source_homepage).hostname in {"www.federalreserve.gov", "www.bls.gov", "www.eia.gov", "www.ecb.europa.eu", "www.bea.gov"}
    score = analysis["asset_scores"].get(lead, 0)
    d.update(assets=assets, asset_scores=analysis["asset_scores"], asset_reasons=analysis["asset_reasons"],
             asset_evidence=analysis["asset_evidence"], relevance_score=score,
             topic=analysis["topics"].get(lead,"弱关联"), reason=analysis["asset_reasons"].get(lead,analysis["rejection"]),
             official=official, attention="high" if score>=85 else "normal", timestamp_known=item.published_at.year>1970,
             via=source.via if source else "unknown", link_label="查看 Google News 索引，跳转媒体文章" if source and source.via=="google_news" else "打开媒体来源")
    return d


def create_router(service):
    router = APIRouter()

    @router.get("/")
    async def home():
        return FileResponse(STATIC / "index.html")

    @router.get("/assets/{name}")
    async def assets(name: str):
        if name not in {"dashboard.css", "dashboard.js", "mark.svg"}:
            raise HTTPException(404)
        return FileResponse(STATIC / name)

    @router.get("/api/hedge/snapshot")
    async def snapshot(q: str = Query("", max_length=150), days: int = Query(3, ge=1, le=30), asset: str = "all", mode: Literal["strict", "related"] = "strict"):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = service.search_items(q, limit=2400, start_at=cutoff) if q.strip() else service.history_items(limit=2400, start_at=cutoff)
        # Use upstream deduplication for the working set as well as live ingestion.
        selected, signatures = [], []
        weak_count = 0
        for row in rows:
            d = decorate(row, mode, asset)
            if not d["assets"]:
                weak_count += 1
                continue
            if not relevant(row): continue
            if service._is_duplicate_signature(row.published_at, row.title, signatures): continue
            signatures.append((row.published_at, service._normalized_title(row.title), service._title_tokens(row.title)))
            selected.append(d)
        return {"items": selected[:1000], "filter": {"mode":mode,"scanned":len(rows),"weak_hidden":weak_count,"matched":len(selected),"note":"规则相关性分，不代表价格影响或概率"}, "generated_at": datetime.now(timezone.utc).isoformat(), "health": service.health_status(), "sources": source_status(), "limit":1000}

    def source_status():
        return [{"name":s.name, "url":s.feed_url, "homepage":s.homepage, "via":s.via, "access_note":"Google News 收录的公开标题，非媒体官方推送；索引和跳转可能延迟，全文可能需订阅。" if s.via == "google_news" else "媒体 / 官方公开 RSS 标题，全文访问遵循来源网站要求。", "kind":s.kind, "category":s.category, "state":"pending", "interval_seconds":20 if s.kind=="json" else 60, **SOURCE_HEALTH.get(s.name,{})} for s in SOURCES]

    @router.get("/api/hedge/sources")
    async def sources():
        return {"sources":source_status()}

    @router.get("/api/hedge/brief")
    async def brief(asset: str = "all", publisher: str = "all", mode: Literal["strict", "related"] = "strict"):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        rows = service.history_items(limit=2400, start_at=cutoff)
        current = [decorate(r, mode, asset) for r in rows if relevant(r)]
        current = [r for r in current if r["assets"]]
        if asset != "all": current = [r for r in current if asset in r["assets"]]
        if publisher != "all": current = [r for r in current if r["source_name"] == publisher]
        groups = []
        for topic in ["宏观政策", "美股指数", "地缘与贸易", "加密市场", "能源供需"]:
            matched = [r for r in current if r["topic"] == topic]
            matched.sort(key=lambda r:(r["attention"]=="high",r["published_at"]), reverse=True)
            selected, keys, signatures, publisher_counts = [], set(), [], {}
            for item in matched:
                key = event_key(item)
                if key in keys or (publisher=="all" and publisher_counts.get(item["source_name"],0)>=3): continue
                stamp=datetime.fromisoformat(item["published_at"])
                if service._is_duplicate_signature(stamp,item["title_original"],signatures): continue
                signatures.append((stamp,service._normalized_title(item["title_original"]),service._title_tokens(item["title_original"])))
                keys.add(key)
                publisher_counts[item["source_name"]]=publisher_counts.get(item["source_name"],0)+1
                selected.append(item)
                if len(selected) == 8: break
            if selected: groups.append({"topic":topic,"count":len(matched),"items":selected,"note":selected[0]["reason"]})
        return {"generated_at":datetime.now(timezone.utc).isoformat(),"window_hours":24,"mode":mode,"count":len(current),"groups":groups,"method":"规则归类 + 原标题 / 机器翻译，不生成未经来源支持的事实"}

    @router.get("/api/hedge/translate/{item_id}")
    async def translate(item_id: str):
        with service._store._connect() as connection:
            row = connection.execute("SELECT title,title_zh,source_name FROM alerts WHERE id=?", (item_id,)).fetchone()
        if not row or row["source_name"] not in ACTIVE_SOURCE_NAMES: raise HTTPException(404)
        title, translated = row["title"], row["title_zh"]
        if contains_cjk(title): return {"title":title,"status":"original_zh"}
        if translated and translated != title and contains_cjk(translated): return {"title":translated,"status":"translated"}
        async with TRANSLATIONS:
            translated = await asyncio.to_thread(translate_text_to_chinese, title[:450])
        if translated != title and contains_cjk(translated):
            with service._store._connect() as connection:
                connection.execute("UPDATE alerts SET title_zh=? WHERE id=?", (translated,item_id))
            return {"title":translated,"status":"translated"}
        return {"title":title,"status":"unavailable"}

    @router.get("/api/hedge/integrations")
    async def integrations():
        return {"plan":"free","paid_connected":False,"push_connected":False,"upgrade":"reserved","adapters":["licensed-news-push","licensed-translation"],"note":"付费入口已预留，尚未订阅、扣费或连接付费数据。"}

    return router
