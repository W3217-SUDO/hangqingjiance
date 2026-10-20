"""Crossmarket Pulse extension, added 2026-10-20. Uses the upstream pipeline/store/SSE."""
from __future__ import annotations
import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from .config import SOURCES
from .fetcher import SOURCE_HEALTH
from .translation import translate_text_to_chinese, contains_cjk

ASSETS = ["US30", "US500", "BTC", "ETH", "XBR", "XTI"]
STATIC = Path(__file__).parent / "static"
TRANSLATIONS = asyncio.Semaphore(3)


def relevant(item):
    title = item.title.lower()
    if re.search(r"技术刘|期货热图|会员专享|点击订阅|限时优惠|开户返|广告推广", title):
        return False
    personal = re.search(r"\b(tennis|football|soccer|golf|singer|celebrity|monfils)\b|网球|足球|婚姻|离婚|分居|球星", title)
    financial = re.search(r"\b(oil|crude|inflation|interest rate|earnings|revenue|billion|stock|bitcoin)\b|原油|通胀|财报|营收|股价|比特币", title)
    return not personal or bool(financial)


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


def decorate(item):
    d = item.as_dict("en")
    title = item.title.lower()
    assets = set()
    topic, reason = "全球动态", "持续关注事件进展与原始披露。"
    macro = re.search(r"\b(fed|fomc|powell|cpi|ppi|inflation|payrolls?|employment|interest rates?|gdp|treasury|dollar|yields?|tariffs?)\b|美联储|鲍威尔|通胀|利率|非农|就业|关税|美债|美元指数|美元流动性|央行", title)
    energy = re.search(r"\b(oil|crude|brent|wti|opec|petroleum|hormuz)\b|原油|石油|布伦特|欧佩克|霍尔木兹|油价|减产", title)
    crypto = re.search(r"\b(crypto|bitcoin|btc|ethereum|ether|eth|stablecoin|blockchain)\b|比特币|以太|加密|稳定币|区块链", title) or item.source_name in {"CoinDesk Markets", "Cointelegraph"}
    geo = re.search(r"\b(war|missile|attack|sanction|iran|russia|ukraine|israel|ceasefire)\b|战争|导弹|袭击|制裁|伊朗|俄罗斯|乌克兰|以色列|停火", title)
    if crypto:
        if re.search(r"\b(bitcoin|btc)\b|比特币", title): assets.add("BTC")
        if re.search(r"\b(ethereum|ether|eth)\b|以太", title): assets.add("ETH")
        if not assets: assets.update(["BTC", "ETH"])
        topic, reason = "加密市场", "关注监管披露、ETF 资金流、交易所与链上事件。"
    if macro or item.source_category in {"macro", "policy"}:
        assets.update(["US30", "US500", "BTC", "ETH"])
        topic, reason = "宏观政策", "关注利率、美元流动性与风险资产联动；须核对数据原值与预期。"
    if energy or item.source_category == "energy":
        assets.update(["XBR", "XTI"])
        topic, reason = "能源供需", "关注原油产量、库存、需求与运输；XBR / XTI 分别对应布伦特 / WTI。"
    if geo:
        assets.update(["US30", "US500", "XBR", "XTI"])
        topic, reason = "地缘与贸易", "关注事件后续及能源供应、运输和风险偏好的关联。"
    if not assets and item.source_category != "world":
        # Broad market news is a candidate for the index watchlist, not a price forecast.
        assets.update(["US30", "US500"])
    official = urlparse(item.source_homepage).hostname in {"www.federalreserve.gov", "www.bls.gov", "www.eia.gov", "www.ecb.europa.eu"}
    high = bool(re.search(r"\b(fomc|cpi|nonfarm|opec|hormuz|war|rate cut|rate hike|etf|hack|exploit|emergency)\b|利率决议|非农|通胀|降息|加息|减产|战争|袭击|霍尔木兹|被盗|紧急", title)) or "source_important" in item.matched_terms
    d.update(assets=[a for a in ASSETS if a in assets], topic=topic, reason=reason, official=official, attention="high" if high else "normal", timestamp_known=item.published_at.year > 1970)
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
    async def snapshot(q: str = Query("", max_length=150), days: int = Query(3, ge=1, le=30), asset: str = "all"):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = service.search_items(q, limit=600, start_at=cutoff) if q.strip() else service.history_items(limit=600, start_at=cutoff)
        # Use upstream deduplication for the working set as well as live ingestion.
        selected, signatures = [], []
        for row in rows:
            if not relevant(row): continue
            if service._is_duplicate_signature(row.published_at, row.title, signatures): continue
            signatures.append((row.published_at, service._normalized_title(row.title), service._title_tokens(row.title)))
            d = decorate(row)
            if asset != "all" and asset not in d["assets"]: continue
            selected.append(d)
        return {"items": selected, "generated_at": datetime.now(timezone.utc).isoformat(), "health": service.health_status(), "sources": source_status(), "limit":600}

    def source_status():
        return [{"name":s.name, "url":s.feed_url, "kind":s.kind, "category":s.category, "state":"pending", "interval_seconds":20 if s.kind=="json" else 60, **SOURCE_HEALTH.get(s.name,{})} for s in SOURCES]

    @router.get("/api/hedge/sources")
    async def sources():
        return {"sources":source_status()}

    @router.get("/api/hedge/brief")
    async def brief(asset: str = "all"):
        rows = service.recent_items(limit=500)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        current = [decorate(r) for r in rows if r.published_at >= cutoff and relevant(r)]
        if asset != "all": current = [r for r in current if asset in r["assets"]]
        groups = []
        for topic in ["宏观政策", "地缘与贸易", "加密市场", "能源供需", "全球动态"]:
            matched = [r for r in current if r["topic"] == topic]
            matched.sort(key=lambda r:(r["attention"]=="high",r["published_at"]), reverse=True)
            selected, keys = [], set()
            for item in matched:
                key = event_key(item)
                if key in keys: continue
                keys.add(key)
                selected.append(item)
                if len(selected) == 3: break
            if selected: groups.append({"topic":topic,"count":len(matched),"items":selected,"note":selected[0]["reason"]})
        return {"generated_at":datetime.now(timezone.utc).isoformat(),"window_hours":24,"count":len(current),"groups":groups,"method":"规则归类 + 原标题 / 机器翻译，不生成未经来源支持的事实"}

    @router.get("/api/hedge/translate/{item_id}")
    async def translate(item_id: str):
        with service._store._connect() as connection:
            row = connection.execute("SELECT title,title_zh FROM alerts WHERE id=?", (item_id,)).fetchone()
        if not row: raise HTTPException(404)
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
