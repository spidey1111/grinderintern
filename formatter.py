from datetime import datetime
import pytz

TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

# Import score_vc_tier từ scraper
try:
    from scraper import score_vc_tier, TIER1_VCS, TIER2_VCS
except ImportError:
    def score_vc_tier(s): return 0


def assess_farm_priority(deal: dict) -> str:
    score = 0
    amount_str = str(deal.get("amount", "")).lower().replace(",", "").replace("$", "").strip()
    round_type = str(deal.get("round", "")).lower()
    token_status = str(deal.get("token_status", "")).lower()
    investors = str(deal.get("investors", ""))
    campaigns = deal.get("campaigns", [])

    # Seed/Pre-seed chưa có token = tự động High
    is_early_round = any(x in round_type for x in ["seed", "pre-seed", "preseed", "private"])
    has_no_token = not token_status or "pre" in token_status or token_status in ["", "none", "null", "no"]
    if is_early_round and has_no_token:
        score += 4

    # Funding size
    try:
        if "m" in amount_str:
            amount = float(amount_str.replace("m", "").strip())
            if amount >= 20:
                score += 2
            elif amount >= 5:
                score += 1
    except Exception:
        pass

    # VC tier
    vc_score = score_vc_tier(investors)
    score += vc_score

    # Active campaigns
    if campaigns and "⚪" not in campaigns[0]:
        score += 2

    if score >= 6:
        return "🔴 High"
    elif score >= 3:
        return "🟡 Medium"
    else:
        return "🟢 Low"


def format_social_links(deal: dict) -> str:
    parts = []
    website = deal.get("website", "")
    twitter = deal.get("twitter", "")
    discord = deal.get("discord", "")

    if website:
        parts.append(f"[🌐 Website]({website})")
    if twitter:
        tw = twitter if twitter.startswith("http") else f"https://x.com/{twitter.lstrip('@')}"
        parts.append(f"[🐦 Twitter]({tw})")
    if discord:
        parts.append(f"[💬 Discord]({discord})")

    return " · ".join(parts) if parts else ""


def format_token_status(deal: dict) -> str:
    token = str(deal.get("token_status", "")).strip()
    if not token or token.lower() in ["", "none", "null", "no"]:
        return "Chưa có token"
    return token


def format_single_deal(i: int, deal: dict) -> str:
    name = deal.get("name", "N/A")
    amount = deal.get("amount", "") or "Chưa công bố"
    round_type = deal.get("round", "") or ""
    investors = deal.get("investors", "") or "Chưa công bố"
    date = deal.get("date", "") or datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    sector = deal.get("sector", "") or "N/A"
    description = deal.get("description", "") or "Chưa có mô tả."
    campaigns = deal.get("campaigns", [])

    priority = assess_farm_priority(deal)
    token_status = format_token_status(deal)
    social_links = format_social_links(deal)

    # Gọi vốn: gộp amount + round
    funding_str = amount
    if round_type:
        funding_str = f"{amount} · {round_type}"

    lines = [
        f"───────────────────",
        f"*#{i} — {name}*",
    ]

    if social_links:
        lines.append(social_links)

    lines += [
        f"",
        f"💰 *Gọi vốn:* {funding_str}",
        f"🏦 *Quỹ đầu tư:* {investors}",
        f"📅 *Ngày:* {date}",
        f"🏷 *Lĩnh vực:* {sector}",
        f"🪙 *Token:* {token_status}",
        f"",
        f"📝 *Mô tả:* {description[:250]}{'...' if len(description) > 250 else ''}",
        f"",
        f"🎯 *Farm priority:* {priority}",
        f"",
        f"*Campaigns đang chạy:*",
    ]

    for c in campaigns:
        lines.append(f"  {c}")

    return "\n".join(lines)


def format_report(deals: list[dict]) -> str:
    now = datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M")
    header = (
        f"📊 *BORING GRINDER — FUNDING REPORT*\n"
        f"🕐 {now} GMT+7  |  {len(deals)} dự án\n"
    )
    parts = [header]
    for i, deal in enumerate(deals, 1):
        parts.append(format_single_deal(i, deal))
    parts.append("───────────────────")
    return "\n".join(parts)


def has_real_campaigns(deal: dict) -> bool:
    """Kiểm tra dự án có campaign thật không"""
    campaigns = deal.get("campaigns", [])
    if not campaigns:
        return False
    return not (len(campaigns) == 1 and "⚪" in campaigns[0])


def format_farm_checklist(deal: dict) -> str:
    """Format chi tiết checklist farm cho inline button callback"""
    name = deal.get("name", "N/A")
    campaigns = deal.get("campaigns", [])
    twitter = deal.get("twitter", "")
    website = deal.get("website", "")
    discord = deal.get("discord", "")

    # Không có campaign thật
    if not has_real_campaigns(deal):
        return None

    lines = [
        f"📋 *CHECKLIST FARM — {name}*",
        f"───────────────────",
        f"",
        f"*Campaigns phát hiện:*",
    ]
    for c in campaigns:
        lines.append(f"• {c}")

    lines += [f"", f"*Hành động gợi ý:*"]
    campaign_text = " ".join(campaigns).lower()

    if "testnet" in campaign_text:
        lines += [
            f"🧪 *Testnet:*",
            f"  → Vào app testnet, connect wallet",
            f"  → Thực hiện swap/bridge/deploy nhỏ",
            f"  → Lặp lại mỗi tuần để tạo on-chain history",
        ]
    if "mainnet" in campaign_text:
        lines += [
            f"🌐 *Mainnet:*",
            f"  → Dùng sản phẩm thật trên mainnet",
            f"  → Tạo volume giao dịch đều đặn",
            f"  → Càng sớm càng tốt trước TGE",
        ]
    if "waitlist" in campaign_text or "early access" in campaign_text:
        lines += [
            f"📝 *Waitlist/Early access:*",
            f"  → Điền form đăng ký sớm",
            f"  → Kết nối wallet nếu yêu cầu",
        ]
    if "airdrop" in campaign_text:
        lines += [
            f"🪂 *Airdrop:*",
            f"  → Theo dõi thông báo chính thức",
            f"  → Hoàn thành các task được liệt kê",
        ]
    if "points" in campaign_text or "rewards" in campaign_text:
        lines += [
            f"⭐ *Points/Rewards:*",
            f"  → Tham gia sớm để tích điểm",
            f"  → Check leaderboard thường xuyên",
            f"  → Dùng app đều đặn để maximize points",
        ]
    if "quest" in campaign_text:
        lines += [
            f"🎯 *Quest/Task:*",
            f"  → Vào Galxe/Zealy tìm campaign",
            f"  → Hoàn thành social + on-chain tasks",
        ]
    if "ambassador" in campaign_text:
        lines += [
            f"🤝 *Ambassador:*",
            f"  → Đọc kỹ yêu cầu trước khi apply",
            f"  → Thường cần tạo content hoặc refer",
        ]
    if "node" in campaign_text:
        lines += [
            f"🖥 *Node:*",
            f"  → Kiểm tra yêu cầu phần cứng",
            f"  → Xem xét chi phí vs phần thưởng",
        ]
    if "incentive" in campaign_text:
        lines += [
            f"💰 *Incentive program:*",
            f"  → Đọc điều kiện tham gia",
            f"  → Track rewards thường xuyên",
        ]

    lines += [f"", f"*Social:*"]
    if twitter:
        tw = twitter if twitter.startswith("http") else f"https://x.com/{twitter.lstrip('@')}"
        lines.append(f"  → Follow & bật thông báo: {tw}")
    if discord:
        lines.append(f"  → Join Discord: {discord}")
    if website:
        lines.append(f"  → Website: {website}")

    lines += [f"", f"⚠️ _DYOR — Tự verify thông tin trước khi farm_"]
    return "\n".join(lines)


def format_header(deals: list[dict]) -> str:
    """Header report ngắn gọn"""
    now = datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M")
    return (
        f"📊 *BORING GRINDER — FUNDING REPORT*\n"
        f"🕐 {now} GMT+7  |  {len(deals)} dự án\n"
        f"───────────────────"
    )


def format_single_deal_text(i: int, deal: dict) -> str:
    """Format 1 deal để gửi kèm inline button"""
    return format_single_deal(i, deal)
