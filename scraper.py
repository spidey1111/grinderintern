import httpx
import asyncio
import logging
from datetime import datetime
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
    "digital currency group", "amber group", "sevenx"
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
    if not value:
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                parts = []
                for item in parsed:
                    if isinstance(item, dict):
                        parts.append(item.get("name") or item.get("investorname") or str(item))
                    else:
                        parts.append(str(item))
                return ", ".join(filter(None, parts))
        except Exception:
            pass
        return value.strip()
    elif isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(item.get("name") or item.get("investorname") or str(item))
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
            "lang": "en-US", "draw": "1",
            "columns[0][data]": "projectname", "columns[0][searchable]": "true",
            "columns[0][orderable]": "false", "columns[0][search][value]": "",
            "columns[0][search][regex]": "false",
            "columns[1][data]": "categorylist", "columns[1][searchable]": "true",
            "columns[1][orderable]": "false", "columns[1][search][value]": "",
            "columns[1][search][regex]": "false",
            "columns[2][data]": "fundstagename", "columns[2][searchable]": "true",
            "columns[2][orderable]": "false", "columns[2][search][value]": "",
            "columns[2][search][regex]": "false",
            "columns[3][data]": "fundamount", "columns[3][searchable]": "true",
            "columns[3][orderable]": "true", "columns[3][search][value]": "",
            "columns[3][search][regex]": "false",
            "columns[4][data]": "investorlist", "columns[4][searchable]": "true",
            "columns[4][orderable]": "false", "columns[4][search][value]": "",
            "columns[4][search][regex]": "false",
            "columns[5][data]": "funddate", "columns[5][searchable]": "true",
            "columns[5][orderable]": "true", "columns[5][search][value]": "",
            "columns[5][search][regex]": "false",
            "order[0][column]": "5", "order[0][dir]": "desc",
            "start": "0", "length": "50",
            "search[value]": "", "search[regex]": "false",
            "_": str(int(time.time() * 1000)),
        }
        r = await client.get(url, params=params, headers=HEADERS, timeout=20)
        logger.info(f"CoinCarp status: {r.status_code}")
        if r.status_code == 200:
            response_json = r.json()
            raw_data = response_json.get("data", {})
            if isinstance(raw_data, dict):
                items = raw_data.get("list", [])
            elif isinstance(raw_data, list):
                items = raw_data
            else:
                items = []
            logger.info(f"CoinCarp items: {len(items)}")
            for item in items:
                if not isinstance(item, dict):
                    continue
                round_type = str(item.get("fundstagename") or "")
                if not is_allowed_round(round_type):
                    continue
                investors_raw = item.get("investornames") or ""
                investors_str = str(investors_raw) if investors_raw else "N/A"
                sector_raw = item.get("categorylist") or []
                sector = parse_field_to_str(sector_raw) or "N/A"
                amount_raw = item.get("fundamount") or 0
                if amount_raw and str(amount_raw) not in ["0", ""]:
                    try:
                        amt = float(str(amount_raw))
                        amount_str = f"${amt/1_000_000:.1f}M" if amt >= 1_000_000 else f"${amt:,.0f}"
                    except Exception:
                        amount_str = str(amount_raw)
                else:
                    amount_str = "N/A"
                fund_date_raw = item.get("funddate") or ""
                if fund_date_raw and str(fund_date_raw).isdigit():
                    fund_date = datetime.utcfromtimestamp(int(fund_date_raw)).strftime("%d/%m/%Y")
                else:
                    fund_date = str(fund_date_raw)
                project_code = str(item.get("projectcode") or "")
                project_name = str(item.get("projectname") or "")
                if not project_name:
                    continue
                deals.append({
                    "name": project_name,
                    "amount": amount_str,
                    "round": round_type,
                    "investors": investors_str,
                    "date": fund_date,
                    "sector": sector,
                    "description": "",
                    "website": "",
                    "twitter": "",
                    "discord": "",
                    "token_status": str(item.get("coincode") or ""),
                    "project_code": project_code,
                    "analysis": "",
                })
        logger.info(f"Parsed deals: {len(deals)}")
    except Exception as e:
        logger.warning(f"CoinCarp error: {e}", exc_info=True)
    return deals


async def fetch_project_info(client: httpx.AsyncClient, deal: dict) -> dict:
    """Fetch social links + description từ CoinCarp coin/info API"""
    project_code = deal.get("project_code", "")
    if not project_code:
        return deal
    try:
        api_url = f"https://sapi.coincarp.com/api/v1/market/coin/info?coincode={project_code}&lang=en-US"
        r = await client.get(api_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            # Log full response for first project to debug field names
            logger.info(f"coin/info keys for {deal['name']}: {list(data.keys())}")
            info = data.get("data", {}) or {}
            if isinstance(info, dict):
                logger.info(f"coin/info data keys for {deal['name']}: {list(info.keys())[:20]}")
                # Try all possible field names
                deal["description"] = (
                    info.get("description") or info.get("desc") or
                    info.get("projectdesc") or info.get("intro") or ""
                )
                deal["website"] = (
                    info.get("officialwebsite") or info.get("website") or
                    info.get("weburl") or ""
                )
                deal["twitter"] = (
                    info.get("twitterurl") or info.get("twitter") or
                    info.get("xurl") or ""
                )
                deal["discord"] = (
                    info.get("discordurl") or info.get("discord") or ""
                )
    except Exception as e:
        logger.warning(f"coin/info error for {deal['name']}: {e}")
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
            return []
        # Fetch project info concurrently
        await asyncio.gather(
            *[fetch_project_info(client, d) for d in all_deals],
            return_exceptions=True
        )
    logger.info(f"Done. Total: {len(all_deals)}")
    return all_deals


async def fetch_project_analysis(project_code: str, name: str, website: str, twitter: str) -> str:
    """Fetch và tổng hợp thông tin phân tích từ website + twitter chính thức"""
    texts = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Fetch website
        if website and website.startswith("http"):
            try:
                r = await client.get(website, headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    # Remove scripts and styles
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)
                    # Get meaningful chunk
                    texts.append(f"[Website {website}]\n{text[:3000]}")
            except Exception as e:
                logger.warning(f"Website fetch error for {name}: {e}")

        # Fetch Twitter via Nitter
        if twitter:
            handle = twitter.rstrip("/").split("/")[-1].lstrip("@")
            if handle and len(handle) > 1:
                for nitter in ["https://nitter.net", "https://nitter.privacydev.net"]:
                    try:
                        r = await client.get(f"{nitter}/{handle}", headers=HEADERS, timeout=10)
                        if r.status_code == 200:
                            soup = BeautifulSoup(r.text, "html.parser")
                            tweets = [t.get_text(strip=True) for t in soup.select(".tweet-content")[:5]]
                            if tweets:
                                texts.append(f"[Twitter @{handle}]\n" + "\n".join(tweets))
                            break
                    except Exception:
                        continue

    if not texts:
        return ""
    return "\n\n".join(texts)
