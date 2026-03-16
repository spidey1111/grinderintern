import httpx
import asyncio
import logging
from bs4 import BeautifulSoup
import re
import time
import json

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://www.coincarp.com/",
}

TIER1_VCS = [
    "a16z", "andreessen horowitz", "paradigm", "sequoia", "binance labs",
    "coinbase ventures", "polychain", "multicoin", "pantera", "dragonfly",
    "framework ventures", "electric capital", "lightspeed", "tiger global",
    "softbank", "delphi digital", "union square ventures", "usv"
]
TIER2_VCS = [
    "animoca", "spartan", "jump", "wintermute", "galaxy", "hashkey",
    "okx ventures", "huobi ventures", "kucoin ventures", "cms holdings",
    "mechanism", "nascent", "variant", "placeholder", "1kx",
    "fabric ventures", "outlier ventures", "blockchain capital", "dcg",
    "digital currency group"
]

ALLOWED_ROUNDS = ["seed", "pre-seed", "preseed", "ico", "ido", "ieo", "private sale", "strategic", "private"]


def is_allowed_round(round_str: str) -> bool:
    if not round_str:
        return True
    r = round_str.lower()
    if re.search(r'series\s+[a-z]', r):
        return False
    if "grant" in r:
        return False
    return any(x in r for x in ALLOWED_ROUNDS)


def score_vc_tier(investors_str: str) -> int:
    if not investors_str:
        return 0
    text = investors_str.lower()
    score = 0
    for vc in TIER1_VCS:
        if vc in text:
            score += 3
    for vc in TIER2_VCS:
        if vc in text:
            score += 1
    return min(score, 5)


def parse_field_to_str(value) -> str:
    """Parse bất kỳ kiểu dữ liệu nào thành string — xử lý str, list, dict"""
    if not value:
        return ""
    if isinstance(value, str):
        # Có thể là JSON string
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                parts = []
                for item in parsed:
                    if isinstance(item, dict):
                        parts.append(item.get("name") or item.get("title") or str(item))
                    else:
                        parts.append(str(item))
                return ", ".join(filter(None, parts))
            elif isinstance(parsed, dict):
                return parsed.get("name") or str(parsed)
        except Exception:
            pass
        return value.strip()
    elif isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(item.get("name") or item.get("title") or str(item))
            else:
                parts.append(str(item))
        return ", ".join(filter(None, parts))
    elif isinstance(value, dict):
        return value.get("name") or str(value)
    return str(value)


async def fetch_coincarp(client: httpx.AsyncClient) -> list[dict]:
    deals = []
    try:
        url = "https://sapi.coincarp.com/api/v1/market/fundraising/list"
        params = {
            "lang": "en-US",
            "draw": "1",
            "columns[0][data]": "projectname",
            "columns[0][searchable]": "true",
            "columns[0][orderable]": "false",
            "columns[0][search][value]": "",
            "columns[0][search][regex]": "false",
            "columns[1][data]": "categorylist",
            "columns[1][searchable]": "true",
            "columns[1][orderable]": "false",
            "columns[1][search][value]": "",
            "columns[1][search][regex]": "false",
            "columns[2][data]": "fundstagename",
            "columns[2][searchable]": "true",
            "columns[2][orderable]": "false",
            "columns[2][search][value]": "",
            "columns[2][search][regex]": "false",
            "columns[3][data]": "fundamount",
            "columns[3][searchable]": "true",
            "columns[3][orderable]": "true",
            "columns[3][search][value]": "",
            "columns[3][search][regex]": "false",
            "columns[4][data]": "investorlist",
            "columns[4][searchable]": "true",
            "columns[4][orderable]": "false",
            "columns[4][search][value]": "",
            "columns[4][search][regex]": "false",
            "columns[5][data]": "funddate",
            "columns[5][searchable]": "true",
            "columns[5][orderable]": "true",
            "columns[5][search][value]": "",
            "columns[5][search][regex]": "false",
            "order[0][column]": "5",
            "order[0][dir]": "desc",
            "start": "0",
            "length": "30",
            "search[value]": "",
            "search[regex]": "false",
            "_": str(int(time.time() * 1000)),
        }

        r = await client.get(url, params=params, headers=HEADERS, timeout=20)
        logger.info(f"CoinCarp status: {r.status_code}")

        if r.status_code == 200:
            response_json = r.json()
            logger.info(f"CoinCarp top keys: {list(response_json.keys()) if isinstance(response_json, dict) else type(response_json).__name__}")

            # data["data"] là list of dicts hoặc list của list
            raw_data = response_json.get("data", [])
            logger.info(f"raw_data type: {type(raw_data).__name__}, len: {len(raw_data) if hasattr(raw_data, '__len__') else 'N/A'}")

            # Log raw_data để xem cấu trúc thật
            try:
                logger.info(f"raw_data sample: {json.dumps(raw_data, ensure_ascii=False)[:1000]}")
            except Exception as e:
                logger.info(f"raw_data sample error: {e}, raw: {str(raw_data)[:500]}")

            # Parse tùy theo cấu trúc
            if isinstance(raw_data, list):
                items = raw_data
            elif isinstance(raw_data, dict):
                # Có thể là {"data": [...]} nested
                inner = raw_data.get("data", [])
                items = inner if isinstance(inner, list) else list(raw_data.values())
            else:
                items = []

            logger.info(f"Items to process: {len(items)}")

            for item in items:
                # Xử lý cả dict và list (array of arrays)
                if isinstance(item, dict):
                    round_type = str(item.get("fundstagename") or item.get("round") or "")
                    investors_str = parse_field_to_str(item.get("investorlist") or item.get("investors")) or "Chưa công bố"
                    sector = parse_field_to_str(item.get("categorylist") or item.get("category")) or "N/A"
                    amount_raw = item.get("fundamount") or item.get("amount") or ""
                    project_name = str(item.get("projectname") or item.get("name") or "")
                    project_code = str(item.get("projectcode") or item.get("code") or "")
                    fund_date = str(item.get("funddate") or item.get("date") or "")
                    description = str(item.get("description") or item.get("projectdesc") or "")
                    website = str(item.get("website") or "")
                    twitter = str(item.get("twitterurl") or item.get("twitter") or "")
                    discord = str(item.get("discordurl") or item.get("discord") or "")
                    token_status = str(item.get("tokentype") or item.get("token") or "")
                elif isinstance(item, list) and len(item) >= 5:
                    # Array format: [projectname, categorylist, fundstagename, fundamount, investorlist, funddate, ...]
                    project_name = str(item[0] or "")
                    sector = parse_field_to_str(item[1]) or "N/A"
                    round_type = str(item[2] or "")
                    amount_raw = item[3] or ""
                    investors_str = parse_field_to_str(item[4]) or "Chưa công bố"
                    fund_date = str(item[5] if len(item) > 5 else "")
                    project_code = str(item[6] if len(item) > 6 else "")
                    description = str(item[7] if len(item) > 7 else "")
                    website = str(item[8] if len(item) > 8 else "")
                    twitter = str(item[9] if len(item) > 9 else "")
                    discord = str(item[10] if len(item) > 10 else "")
                    token_status = ""
                else:
                    logger.warning(f"Skipping item type {type(item).__name__}: {str(item)[:100]}")
                    continue

                if not is_allowed_round(round_type):
                    continue

                if not project_name:
                    continue

                # Parse amount
                if amount_raw and str(amount_raw) not in ["0", "", "None"]:
                    try:
                        amt = float(str(amount_raw).replace(",", "").replace("$", ""))
                        amount_str = f"${amt/1_000_000:.1f}M" if amt >= 1_000_000 else f"${amt:,.0f}"
                    except Exception:
                        amount_str = str(amount_raw)
                else:
                    amount_str = "Chưa công bố"

                coincarp_url = f"https://www.coincarp.com/currencies/{project_code}/" if project_code else ""

                deals.append({
                    "source": "CoinCarp",
                    "name": project_name,
                    "amount": amount_str,
                    "round": round_type,
                    "investors": investors_str,
                    "date": fund_date,
                    "sector": sector,
                    "description": description,
                    "website": website,
                    "twitter": twitter,
                    "discord": discord,
                    "token_status": token_status,
                    "campaigns": [],
                    "coincarp_url": coincarp_url,
                })

        logger.info(f"CoinCarp parsed deals: {len(deals)}")

    except Exception as e:
        logger.warning(f"CoinCarp fetch error: {e}", exc_info=True)
    return deals


async def fetch_coincarp_detail(client: httpx.AsyncClient, deal: dict) -> dict:
    url = deal.get("coincarp_url", "")
    if not url or (deal.get("website") and deal.get("twitter")):
        return deal
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if ("twitter.com" in href or "x.com" in href) and not deal.get("twitter"):
                    deal["twitter"] = href
                elif "discord.gg" in href and not deal.get("discord"):
                    deal["discord"] = href
                elif (href.startswith("http") and
                      not any(x in href for x in ["coincarp", "twitter", "discord", "t.me", "telegram"]) and
                      not deal.get("website")):
                    deal["website"] = href
            if not deal.get("description"):
                desc = soup.select_one("[class*='description'], [class*='about'], .project-desc")
                if desc:
                    deal["description"] = desc.get_text(strip=True)[:400]
    except Exception as e:
        logger.warning(f"CoinCarp detail error for {deal.get('name')}: {e}")
    return deal


async def fetch_project_campaigns(client: httpx.AsyncClient, deal: dict) -> dict:
    campaigns = []
    name = deal.get("name", "")
    campaign_keywords = {
        "testnet": "🧪 Testnet campaign",
        "mainnet": "🌐 Mainnet launch — tương tác sớm",
        "waitlist": "📝 Waitlist / Early access",
        "airdrop": "🪂 Airdrop campaign",
        "points": "⭐ Points / Rewards program",
        "quest": "🎯 Quest / Task campaign",
        "ambassador": "🤝 Ambassador program",
        "node": "🖥 Node / Validator program",
        "incentive": "💰 Incentive program",
        "early access": "🔑 Early access",
        "community round": "👥 Community round",
    }

    website = deal.get("website", "")
    if website and website.startswith("http"):
        try:
            r = await client.get(website, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ", strip=True).lower()
                for kw, label in campaign_keywords.items():
                    if kw in text and label not in campaigns:
                        campaigns.append(label)
        except Exception as e:
            logger.warning(f"Website fetch error for {name}: {e}")

    twitter = deal.get("twitter", "")
    if twitter:
        handle = twitter.rstrip("/").split("/")[-1].lstrip("@")
        if handle and handle != "twitter.com" and handle != "x.com":
            for nitter_host in ["https://nitter.net", "https://nitter.privacydev.net"]:
                try:
                    r = await client.get(f"{nitter_host}/{handle}", headers=HEADERS, timeout=10)
                    if r.status_code == 200:
                        tweet_text = " ".join([
                            t.get_text(strip=True)
                            for t in BeautifulSoup(r.text, "html.parser").select(".tweet-content")[:10]
                        ]).lower()
                        for kw, label in campaign_keywords.items():
                            tw_label = label + " (Twitter)"
                            if kw in tweet_text and tw_label not in campaigns and label not in campaigns:
                                campaigns.append(tw_label)
                        break
                except Exception:
                    continue

    if not campaigns:
        campaigns = ["⚪ Chưa tìm thấy campaign — theo dõi Twitter/Discord"]

    deal["campaigns"] = campaigns
    return deal


def deduplicate(deals: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for deal in deals:
        name = deal.get("name", "").lower().strip()
        if name and name not in seen:
            seen.add(name)
            unique.append(deal)
    return unique


async def fetch_funding_news() -> list[dict]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        all_deals = await fetch_coincarp(client)
        all_deals = deduplicate(all_deals)
        logger.info(f"After dedup: {len(all_deals)} deals")

        if not all_deals:
            logger.warning("No deals found from CoinCarp")
            return []

        detail_tasks = [fetch_coincarp_detail(client, d) for d in all_deals if d.get("coincarp_url")]
        if detail_tasks:
            await asyncio.gather(*detail_tasks, return_exceptions=True)

        await asyncio.gather(
            *[fetch_project_campaigns(client, d) for d in all_deals],
            return_exceptions=True
        )

    logger.info(f"Done. Total deals: {len(all_deals)}")
    return all_deals
