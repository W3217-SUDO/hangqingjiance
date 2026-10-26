"""Auditable headline relevance rules, 2026-10-25.

Scores rank explicit subject/event matches, not price impact, probabilities or advice.
Publisher names and feed categories never grant instrument relevance on their own.
"""
from functools import lru_cache
import re

ASSETS = ("US30", "US500", "BTC", "ETH", "XBR", "XTI")
THRESHOLDS = {"strict": 75, "related": 45}


def hit(pattern, text):
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else ""


@lru_cache(maxsize=12000)
def analyze(title: str, source_name: str = "") -> dict:
    scores, reasons, evidence, topics = {}, {}, {}, {}
    def add(assets, score, reason, topic, *terms):
        for asset in assets:
            if score > scores.get(asset, 0):
                scores[asset], reasons[asset], topics[asset] = score, reason, topic
                evidence[asset] = list(dict.fromkeys(t for t in terms if t))

    noise = hit(r"\b(tennis|football|soccer|golf|celebrity|horoscope|sponsored|advertorial)\b|技术刘|期货热图|会员专享|点击订阅|限时优惠|开户返|广告推广|离婚|分居", title)
    explainer = hit(r"\b(how to|what is|what are|beginner.s guide|best stocks to buy|best coins|top \d+ coins|price prediction|should you buy)\b|投资入门|如何购买|值得买吗|价格预测", title)
    if noise or explainer:
        return {"asset_scores": {}, "asset_reasons": {}, "asset_evidence": {}, "topics": {}, "rejection": "推广、生活、体育或入门选题"}

    # Lowercase English "us" is a pronoun, not an anchor for US macro data.
    us = hit(r"\bu\.s\.(?=\s|$)|united states|american|federal reserve|\bfomc\b|\bfed\b|powell|美国|美联储|鲍威尔|美债", title)
    if not us and re.search(r"\bUS\b", title):
        us = "US"
    if source_name.startswith(("Federal Reserve", "BLS", "BEA")):
        us = us or source_name
    data = hit(r"\b(cpi|pce|ppi|gdp|nonfarm|payrolls?|adp|jolts|ism)\b|inflation|jobless claims|retail sales|employment situation|consumer price index|personal income|personal consumption|unemployment rate|trade balance|durable goods|非农|通胀|就业人数|失业率|零售销售|消费者价格指数", title)
    policy_subject = hit(r"federal reserve|\bfomc\b|\bfed\b|powell|美联储|鲍威尔", title)
    policy_event = hit(r"interest rates?|rate (?:cut|hike|decision|hold|pause)|cuts? rates?|hikes? rates?|monetary policy|balance sheet|quantitative|taper|dot plot|minutes|projections|利率|降息|加息|缩表|扩表|货币政策|会议纪要", title)
    indicator = hit(r"\b(cpi|pce|ppi|gdp|non[ -]?farm|payrolls?|adp|jolts|ism)\b|jobless claims|retail sales|employment situation|consumer price index|personal income|personal consumption|unemployment rate|trade balance|durable goods|非农|就业人数|失业率|零售销售|消费者价格指数", title)
    release = hit(r"rise|fall|cool|heat|accelerat|slow|above|below|unexpected|report|data|release|上涨|下跌|放缓|升温|高于|低于|数据|公布", title)
    if us and data and (indicator or release):
        add(("US30","US500"), 92, "美国关键经济数据或通胀 / 增长信息", "宏观政策", us, data)
        add(("BTC","ETH"), 78, "美国宏观数据对应美元利率 / 流动性预期", "宏观政策", us, data)
    if policy_subject and policy_event:
        add(("US30","US500","BTC","ETH"), 94, "明确涉及美联储利率、政策路径或流动性", "宏观政策", policy_subject, policy_event)
    rates = hit(r"(?:u\.?s\.?\s+)?treasury yields?|\b(?:2|10|30)[ -]year (?:treasury|yield)|dollar index|\bdxy\b|美债收益率|美国国债收益率|美元指数", title)
    movement = hit(r"\b(rises?|falls?|drops?|dips?|jumps?|surges?|slips?|climbs?|rall(?:y|ies)|sell.?off|plunges?|cuts?|hikes?|halts?|record|hits?|gains?|loses?|slumps?|tumbles?)\b|走高|走低|上涨|下跌|飙升|暴跌|新高|新低", title)
    if rates and movement:
        add(("US30","US500","BTC","ETH"), 83, "美债收益率或美元指数的明确变化", "宏观政策", rates, movement)
    fiscal = hit(r"tariffs?|debt ceiling|government shutdown|debt default|关税|债务上限|政府停摆|债务违约", title)
    if us and fiscal:
        tariff = hit(r"tariffs?|关税", title)
        decision = hit(r"(?:imposes?|raises?|cuts?|suspends?|lifts?|blocks?|strikes down|announces?).{0,18}tariffs?|tariffs?.{0,20}(?:hike|increase|cuts?|suspend)|trade (?:deal|war)|最高法院.*关税|(?:加征|取消|暂停|提高).{0,10}关税", title)
        if not tariff or decision:
            add(("US30","US500"), 86, "美国贸易 / 财政政策决定，具有大盘风险传导路径", "地缘与贸易", us, fiscal, decision)
        else:
            add(("US30","US500"), 50, "仅提及美国关税背景，未发现新的政策决定", "地缘与贸易", us, fiscal)

    dow = hit(r"\bdow(?: jones)?\b|\bdjia\b|\bus30\b|道琼斯|道指", title)
    if hit(r"dow (?:inc|chemical|materials)", title):
        dow = ""
    sp = hit(r"s\s*&\s*p\s*500|s&p|s and p 500|\bus500\b|标普", title)
    index_event = movement or hit(r"futures?|index|stocks?|equities|record|期货|指数|股市", title)
    if dow and index_event:
        add(("US30",), 88, "标题直接涉及道琼斯指数或其期货", "美股指数", dow, index_event)
    if sp and index_event:
        add(("US500",), 88, "标题直接涉及标普 500 或其期货", "美股指数", sp, index_event)
    broad = hit(r"u\.?s\.? (?:stock|equities|equity)|wall street|美股|美国股市", title)
    if broad and (movement or hit(r"futures?|opens?|closes?|期货|开盘|收盘", title)):
        add(("US30","US500"), 87, "美国大盘 / 股指期货的明确交易动态", "美股指数", broad, movement or index_event)
    mega = hit(r"\b(apple|aapl|microsoft|msft|nvidia|nvda|amazon|amzn|alphabet|googl|meta|tesla|tsla|broadcom|avgo)\b|苹果|微软|英伟达|亚马逊|特斯拉", title)
    earnings = hit(r"earnings|guidance|revenue|profits?|results|antitrust|export ban|财报|业绩指引|营收|利润|反垄断|出口禁令", title)
    if mega and earnings:
        add(("US500",), 80, "大型美股公司的财报 / 指引 / 重大政策事件；仍需核对指数传导", "美股指数", mega, earnings)
        add(("US30",), 48, "大型公司事件仅作大盘背景，未确认对道指的直接关联", "美股指数", mega, earnings)

    oil = hit(r"\b(oil|crude|brent|wti|opec|petroleum)\b|原油|布伦特|欧佩克|石油", title)
    oil_event = hit(r"inventor\w*|stockpiles?|output|production|supply|demand|exports?|imports?|barrels?|\bbpd\b|pipeline|refiner\w*|cuts?|hikes?|sanction\w*|库存|产量|供给|需求|出口|进口|减产|增产|炼厂", title)
    oil_price_event = hit(r"\b(?:oil|crude|brent|wti)(?:[ -](?:prices?|futures?|crude|oil)){0,3}.{0,18}\b(?:falls?|rises?|drops?|dips?|jumps?|surges?|slips?|climbs?|rall(?:y|ies)|plunges?|hits?|gains?|loses?|slumps?|tumbles?|above|below|trades?)\b|(?:原油|布伦特|油价).{0,12}(?:上涨|下跌|跌破|涨破|飙升|暴跌|新高|新低)", title)
    oil_event = oil_event or oil_price_event
    if oil and oil_event and not hit(r"olive oil|cooking oil|hair oil|essential oil|食用油|橄榄油", title):
        add(("XBR","XTI"), 91, "原油价格、供需、产量、库存或炼化事件", "能源供需", oil, oil_event)
    route = hit(r"hormuz|red sea|suez|oilfield|oil field|oil terminal|oil tanker|oil pipeline|霍尔木兹|红海|苏伊士|油田|油轮|输油管", title)
    disruption = hit(r"attack|strike|block\w*|clos\w*|halt|disrupt\w*|reopen|ceasefire|sanction\w*|袭击|封锁|关闭|中断|停火|重开|制裁", title)
    if route and disruption:
        add(("XBR","XTI"), 96, "明确涉及原油供应设施或关键运输通道受扰 / 恢复", "地缘与贸易", route, disruption)
    major_war = hit(r"iran|伊朗", title) and hit(r"u\.?s\.?|united states|美国|israel|以色列", title) and hit(r"declares? war|war begins|launch\w* (?:a )?(?:war|strikes)|military strikes|开战|宣战|军事打击", title)
    if major_war:
        add(("XBR","XTI","US30","US500"), 88, "涉及美伊 / 以伊重大军事升级，需继续核实供应与大盘反应", "地缘与贸易", major_war)

    btc = hit(r"\b(bitcoin|btc)\b|比特币", title)
    eth = hit(r"\b(ethereum|ether|eth)\b|以太坊|以太币", title)
    crypto_event = movement or hit(r"inflows?|outflows?|approv\w*|reject\w*|files?|filing|liquidat\w*|hack\w*|exploit\w*|outage|upgrade|hard fork|staking|validators?|funding rates?|open interest|buys?|sells?|purchases?|treasury|流入|流出|批准|驳回|清算|被盗|升级|质押|买入|卖出", title)
    for asset, subject in (("BTC",btc),("ETH",eth)):
        if subject and crypto_event:
            add((asset,), 90, "明确涉及该币种的资金流、政策、网络事件或交易变化", "加密市场", subject, crypto_event)
        elif subject:
            add((asset,), 50, "提及该币种，但标题未显示具体市场催化事件", "加密市场", subject)
    systemic = hit(r"binance|coinbase|tether|\busdt\b|\busdc\b|stablecoin|币安|稳定币", title)
    crisis = hit(r"depeg|bankrupt\w*|insolven\w*|withdrawal\w* (?:halt|suspend)|halts? withdrawals?|exploit|hack|脱锚|破产|暂停提现|被盗", title)
    if systemic and crisis:
        add(("BTC","ETH"), 93, "关键交易平台 / 稳定币出现明确流动性或安全事件", "加密市场", systemic, crisis)

    other_policy = hit(r"\becb\b|bank of england|european central bank|欧洲央行|英国央行", title)
    if other_policy and policy_event:
        add(("US30","US500","BTC","ETH"), 55, "海外央行政策仅作间接利率背景", "宏观政策", other_policy, policy_event)
    opinion = hit(r"\b(could|might|predict\w*|analyst\w*|strategist\w*)\b|分析师|或将|可能涨|可能跌", title)
    if opinion and not source_name.startswith("Federal Reserve"):
        scores = {asset:min(score,65) for asset,score in scores.items()}
        reasons = {asset:"观点 / 情景预期，非已确认事件；"+reason for asset,reason in reasons.items()}
    regional_focus = hit(r"^(?:asian|european|japanese|chinese|indian|shares .{0,30}(?:asia|europe)|oil prices, .{0,60}rupee)", title)
    if regional_focus and not (dow or sp):
        for asset in ("US30", "US500"):
            if asset in scores:
                scores[asset] = min(scores[asset], 60)
                reasons[asset] = "海外区域市场背景，标题未直接报告美国指数事件"
    return {"asset_scores":scores,"asset_reasons":reasons,"asset_evidence":evidence,"topics":topics,"rejection":"未发现明确的品种与事件组合" if not scores else ""}


def select_assets(analysis, mode="strict", asset="all"):
    floor = THRESHOLDS.get(mode, THRESHOLDS["strict"])
    return [a for a in ASSETS if analysis["asset_scores"].get(a,0)>=floor and (asset=="all" or a==asset)]
