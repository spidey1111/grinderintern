from datetime import datetime
import pytz

TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


def assess_farm_priority(deal: dict) -> str:
    """Tự động đánh giá mức độ ưu tiên farm dựa trên các yếu tố có sẵn"""
    score = 0
    amount_str = str(deal.get("amount", "")).lower().replace(",", "")

    # Funding size
    try:
        if "m" in amount_str:
            amount = float(amount_str.replace("m", "").replace("$", "").strip())
            if amount >= 20:
                score += 3
            elif amount >= 5:
                score += 2
            else:
                score += 1
    except:
        pass

    # Round type
    round_type = str(deal.get("round", "")).lower()
    if any(x in round_type for x in ["seed", "pre-seed"]):
        score += 2  # Early stage = more airdrop likely
    elif "series a" in round_type:
        score += 1

    # No token yet = airdrop opportunity
    token_status = str(deal.get("token_status", "")).lower()
    if "no" in token_status or "pre" in token_status or token_status == "":
        score += 2

    # Sector bonus
    sector = str(deal.get("sector", "")).lower()
    if any(x in sector for x in ["defi", "layer", "infra", "zk", "ai"]):
        score += 1

    if score >= 6:
        return "🔴 High"
    elif score >= 3:
        return "🟡 Medium"
    else:
        return "🟢 Low"


def assess_token_status(deal: dict) -> str:
    token = str(deal.get("token_status", "")).strip()
    if not token or token.lower() in ["", "none", "null"]:
        return "⚪ Chưa có token (Pre-launch)"
    return f"✅ Đã có token: {token}"


def assess_stage(deal: dict) -> str:
    stage = str(deal.get("stage", "")).strip().lower()
    if "mainnet" in stage:
        return "🌐 Mainnet"
    elif "testnet" in stage:
        return "🧪 Testnet"
    else:
        return "❓ Chưa rõ"


def format_farm_suggestion(deal: dict) -> str:
    """Gợi ý hướng farm dựa trên thông tin có được"""
    suggestions = []
    sector = str(deal.get("sector", "")).lower()
    stage = str(deal.get("stage", "")).lower()
    token_status = str(deal.get("token_status", "")).lower()

    # Pre-launch = airdrop potential
    if not token_status or "pre" in token_status:
        suggestions.append("• Follow X + join Discord sớm (early community points)")

    if "testnet" in stage:
        suggestions.append("• Tham gia testnet, làm task on-chain để tích lũy activity")

    if "mainnet" in stage:
        suggestions.append("• Dùng sản phẩm mainnet thật sự (volume, transactions)")

    if "defi" in sector:
        suggestions.append("• Provide liquidity / swap để tạo on-chain history")

    if "layer" in sector or "infra" in sector:
        suggestions.append("• Deploy contract hoặc bridge assets sang chain mới")

    if "nft" in sector:
        suggestions.append("• Mint early NFT nếu có freemint/whitelist")

    if not suggestions:
        suggestions.append("• Theo dõi announcement channel để cập nhật chương trình farm")

    return "\n".join(suggestions)


def format_single_deal(i: int, deal: dict) -> str:
    name = deal.get("name", "N/A")
    amount = deal.get("amount", "N/A") or "Chưa công bố"
    round_type = deal.get("round", "N/A") or "N/A"
    investors = deal.get("investors", "") or "Chưa công bố"
    date = deal.get("date", "") or datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    sector = deal.get("sector", "") or "N/A"
    description = deal.get("description", "") or "Chưa có mô tả."
    website = deal.get("website", "")
    twitter = deal.get("twitter", "")
    source = deal.get("source", "")

    priority = assess_farm_priority(deal)
    token_status = assess_token_status(deal)
    stage = assess_stage(deal)
    farm_suggestion = format_farm_suggestion(deal)

    lines = [
        f"━━━━━━━━━━━━━━━━━━━━",
        f"*{i}. {name}*",
        f"",
        f"💰 *Gọi vốn:* {amount} | {round_type}",
        f"🏦 *Quỹ đầu tư:* {investors}",
        f"📅 *Ngày:* {date}",
        f"",
        f"🏷 *Lĩnh vực:* {sector}",
        f"📝 *Mô tả:* {description[:200]}{'...' if len(description) > 200 else ''}",
        f"",
        f"🪙 *Token:* {token_status}",
        f"🌐 *Giai đoạn:* {stage}",
        f"",
        f"🎯 *Mức độ ưu tiên farm:* {priority}",
        f"",
        f"🌱 *Gợi ý farm:*",
        farm_suggestion,
    ]

    # Social links
    socials = []
    if website:
        socials.append(f"[Website]({website})")
    if twitter:
        tw = twitter if twitter.startswith("http") else f"https://x.com/{twitter.lstrip('@')}"
        socials.append(f"[X/Twitter]({tw})")

    if socials:
        lines.append(f"")
        lines.append(f"🔗 *Links:* {' | '.join(socials)}")

    if source:
        lines.append(f"📰 *Nguồn:* {source}")

    return "\n".join(lines)


def format_report(deals: list[dict]) -> str:
    now = datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M")

    header = (
        f"📊 *BORING GRINDER — FUNDING REPORT*\n"
        f"🕐 Cập nhật: {now} (GMT+7)\n"
        f"📦 Tổng số dự án: {len(deals)}\n"
    )

    body_parts = [header]

    for i, deal in enumerate(deals, 1):
        body_parts.append(format_single_deal(i, deal))

    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"_Slow. Boring. Still here. 🐢_\n"
        f"_Dùng lệnh /funding để fetch thủ công bất kỳ lúc nào._"
    )
    body_parts.append(footer)

    return "\n".join(body_parts)
