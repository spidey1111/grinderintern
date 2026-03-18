from datetime import datetime
import pytz

TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

TIER1_VCS = [
    "a16z", "andreessen horowitz", "paradigm", "sequoia", "binance labs",
    "coinbase ventures", "polychain", "multicoin", "pantera", "dragonfly",
    "framework ventures", "electric capital", "lightspeed", "tiger global",
    "softbank", "delphi digital"
]
TIER2_VCS = [
    "animoca", "spartan", "jump", "wintermute", "galaxy", "hashkey",
    "okx ventures", "huobi ventures", "kucoin ventures", "mechanism",
    "nascent", "variant", "1kx", "fabric ventures", "outlier ventures",
    "blockchain capital", "dcg", "amber group", "sevenx"
]


def assess_farm_priority(deal: dict) -> str:
    score = 0
    round_type = str(deal.get("round", "")).lower()
    token_status = str(deal.get("token_status", "")).lower()
    investors = str(deal.get("investors", "")).lower()

    is_early = any(x in round_type for x in ["seed", "pre-seed", "preseed", "private"])
    has_no_token = not token_status or token_status in ["", "none", "null"]
    if is_early and has_no_token:
        score += 4

    for vc in TIER1_VCS:
        if vc in investors:
            score += 3
    for vc in TIER2_VCS:
        if vc in investors:
            score += 1
    score = min(score, 9)

    amount_str = str(deal.get("amount", "")).lower().replace("$", "").replace(",", "")
    try:
        if "m" in amount_str:
            amt = float(amount_str.replace("m", "").strip())
            if amt >= 20:
                score += 2
            elif amt >= 5:
                score += 1
    except Exception:
        pass

    if score >= 6:
        return "High"
    elif score >= 3:
        return "Medium"
    else:
        return "Low"


def format_links(deal: dict) -> str:
    parts = []
    website = deal.get("website", "")
    twitter = deal.get("twitter", "")
    discord = deal.get("discord", "")
    if website:
        parts.append(f"[Website]({website})")
    if twitter:
        tw = twitter if twitter.startswith("http") else f"https://x.com/{twitter.lstrip('@')}"
        parts.append(f"[X]({tw})")
    if discord:
        parts.append(f"[Discord]({discord})")
    return " | ".join(parts) if parts else ""


def format_single_deal(i: int, deal: dict) -> str:
    name = deal.get("name", "N/A")
    amount = deal.get("amount", "N/A")
    round_type = deal.get("round", "N/A")
    investors = deal.get("investors", "N/A")
    date = deal.get("date", "")
    sector = deal.get("sector", "N/A")
    description = deal.get("description", "")
    priority = assess_farm_priority(deal)
    links = format_links(deal)

    lines = [
        f"───────────────────",
        f"*{i}. {name}*",
    ]
    if links:
        lines.append(links)
    lines += [
        f"",
        f"Goi von: {amount} | {round_type} | {date}",
        f"Quy dau tu: {investors}",
        f"Sector: {sector}",
        f"Farm priority: {priority}",
    ]
    if description:
        lines += [f"", f"Mo ta: {description[:300]}{'...' if len(description) > 300 else ''}"]

    return "\n".join(lines)


def format_header(deals: list[dict]) -> str:
    now = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    return f"FUNDING REPORT {now}"


def format_single_deal_text(i: int, deal: dict) -> str:
    return format_single_deal(i, deal)


def format_analysis_response(deal: dict, raw_text: str) -> str:
    """Format phần phân tích chi tiết từ raw text đã fetch"""
    name = deal.get("name", "N/A")
    if not raw_text:
        return f"Khong tim thay thong tin chinh thuc cho {name}. Vui long check website/X cua du an."

    # Tóm tắt thông tin có sẵn thành phân tích
    lines = [
        f"PHAN TICH CHI TIET — {name}",
        f"───────────────────",
        f"",
        f"Nguon: thong tin chinh thuc tu website + X cua du an",
        f"",
    ]

    # Extract meaningful content from raw text
    website_content = ""
    twitter_content = ""

    if "[Website" in raw_text:
        parts = raw_text.split("[Twitter")
        website_content = parts[0].replace("[Website", "").strip()
        if len(parts) > 1:
            twitter_content = parts[1].strip()
    else:
        website_content = raw_text

    if website_content:
        # Clean up and take first meaningful chunk
        clean = " ".join(website_content.split())[:1500]
        lines += [f"Tu website chinh thuc:", f"{clean}", f""]

    if twitter_content:
        clean_tw = " ".join(twitter_content.split())[:500]
        lines += [f"Tu X (Twitter):", f"{clean_tw}", f""]

    return "\n".join(lines)
