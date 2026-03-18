from datetime import datetime
import pytz

TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

TIER1_VCS = [
    "a16z", "andreessen horowitz", "paradigm", "sequoia", "binance labs",
    "coinbase ventures", "polychain", "multicoin", "pantera", "dragonfly",
    "framework ventures", "electric capital", "lightspeed"
]
TIER2_VCS = [
    "animoca", "spartan", "jump", "wintermute", "galaxy", "hashkey",
    "okx ventures", "huobi ventures", "kucoin ventures", "mechanism",
    "1kx", "blockchain capital", "dcg", "amber group", "sevenx"
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
            break
    for vc in TIER2_VCS:
        if vc in investors:
            score += 1
            break

    try:
        amt_str = str(deal.get("amount", "")).lower().replace("$", "").replace(",", "")
        if "m" in amt_str:
            amt = float(amt_str.replace("m", "").strip())
            score += 2 if amt >= 20 else (1 if amt >= 5 else 0)
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
    if deal.get("website"):
        parts.append(f"[Website]({deal['website']})")
    if deal.get("twitter"):
        tw = deal["twitter"]
        if not tw.startswith("http"):
            tw = f"https://x.com/{tw.lstrip('@')}"
        parts.append(f"[X]({tw})")
    if deal.get("discord"):
        parts.append(f"[Discord]({deal['discord']})")
    return " | ".join(parts)


def format_single_deal(i: int, deal: dict) -> str:
    name = deal.get("name", "N/A")
    amount = deal.get("amount", "Chưa công bố")
    round_type = deal.get("round", "N/A")
    investors = deal.get("investors", "Chưa công bố")
    date = deal.get("date", "")
    sector = deal.get("sector", "N/A")
    description = deal.get("description", "")
    links = format_links(deal)

    lines = [
        "───────────────────",
        f"*{i}. {name}*",
    ]
    if links:
        lines.append(links)
    lines.append("")
    lines.append(f"Gọi vốn: {amount} | {round_type} | {date}")
    lines.append(f"Quỹ đầu tư: {investors}")
    lines.append(f"Lĩnh vực: {sector}")
    if description:
        desc = description[:300] + ("..." if len(description) > 300 else "")
        lines += ["", f"Mô tả: {desc}"]
    return "\n".join(lines)


def format_header(deals: list[dict]) -> str:
    now = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    return f"FUNDING REPORT {now}"


def format_single_deal_text(i: int, deal: dict) -> str:
    return format_single_deal(i, deal)


def format_analysis_text(deal: dict, raw_content: str) -> str:
    name = deal.get("name", "N/A")
    if not raw_content or not raw_content.strip():
        return (
            f"Phân tích chi tiết — {name}\n"
            f"───────────────────\n\n"
            f"Không tìm thấy nội dung từ website/X chính thức của dự án.\n"
            f"Vui lòng truy cập trực tiếp:\n"
            + (f"Website: {deal.get('website')}\n" if deal.get("website") else "")
            + (f"X: {deal.get('twitter')}\n" if deal.get("twitter") else "")
        )

    lines = [
        f"Phân tích chi tiết — {name}",
        "───────────────────",
        "",
        raw_content.strip()
    ]
    return "\n".join(lines)
