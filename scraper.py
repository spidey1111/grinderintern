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
    "softbank", "delphi digital"
]
TIER2_VCS = [
    "animoca", "spartan", "jump", "wintermute", "galaxy", "hashkey",
    "okx ventures", "huobi ventures", "kucoin ventures", "mechanism",
    "nascent", "variant", "1kx", "fabric ventures", "outlier ventures",
    "blockchain capital", "dcg", "amber group", "sevenx", "multicoin"
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


def parse_field_to_str(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return ", ".join(
                    item.get("name") or item.get("investorname") or str(item)
                    if isinstance(item, dict) else str(item)
                    for item in parsed
                )
        except Exception:
            pass
        return value.strip()
    elif isinstance(value, list):
        return ", ".join(
            item.get("name") or item.get("investorname") or str(item)
            if isinstance(item, dict) else str(item)
            for item in value
        )
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
        if r.status_code != 200:
            logger.warning(f"CoinCarp status: {r.status_code}")
            return deals

        response_json = r.json()
        raw_data = response_json.get("data", {})
        items = raw_data.get("list", []) if isinstance(raw_data, dict) else []
        logger.info(f"CoinCarp items: {len(items)}")

        for item in items:
            if not isinstance(item, dict):
                continue
            round_type = str(item.get("fundstagename") or "")
            if not is_allowed_round(round_type):
                continue

            investors_str = str(item.get("investornames") or "").strip() or "Chưa công bố"
            sector = parse_field_to_str(item.get("categorylist")) or "N/A"

            amount_raw = item.get("fundamount") or 0
            try:
                amt = float(str(amount_raw))
                amount_str = f"${amt/1_000_000:.1f}M" if amt >= 1_000_000 else (f"${amt:,.0f}" if amt > 0 else "Chưa công bố")
            except Exception:
                amount_str = "Chưa công bố"

            fund_date_raw = item.get("funddate") or ""
            if str(fund_date_raw).isdigit():
                fund_date = datetime.utcfromtimestamp(int(fund_date_raw)).strftime("%d/%m/%Y")
            else:
                fund_date = str(fund_date_raw)

            project_name = str(item.get("projectname") or "").strip()
            if not project_name:
                continue

            deals.append({
                "name": project_name,
                "amount": amount_str,
                "round": round_type,
                "investors": investors_str,
                "date": fund_date,
                "sector": sector,
                "description": str(item.get("projectdesc") or ""),
                "website": "",
                "twitter": "",
                "discord": "",
                "token_status": str(item.get("coincode") or ""),
                "project_code": str(item.get("projectcode") or ""),
            })

        logger.info(f"Parsed: {len(deals)} deals")
    except Exception as e:
        logger.error(f"CoinCarp error: {e}", exc_info=True)
    return deals


async def search_project_links(client: httpx.AsyncClient, deal: dict) -> dict:
    """Dùng DuckDuckGo để tìm website + twitter chính thức của dự án"""
    name = deal.get("name", "")
    if not name:
        return deal
    try:
        # Search DuckDuckGo
        search_url = "https://html.duckduckgo.com/html/"
        params = {"q": f"{name} crypto official website twitter"}
        r = await client.post(search_url, data=params, headers={
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded"
        }, timeout=15)

        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            results = soup.select(".result__url")
            for result in results[:5]:
                href = result.get_text(strip=True)
                if not href.startswith("http"):
                    href = "https://" + href
                href_lower = href.lower()
                if "twitter.com" in href_lower or "x.com" in href_lower:
                    if not deal.get("twitter") and name.lower().replace(" ", "") in href_lower:
                        deal["twitter"] = href
                elif "discord" in href_lower:
                    if not deal.get("discord"):
                        deal["discord"] = href
                elif not deal.get("website"):
                    skip = ["coincarp", "cryptorank", "rootdata", "coingecko",
                            "crunchbase", "twitter", "x.com", "discord", "medium",
                            "linkedin", "facebook", "youtube", "telegram"]
                    if not any(s in href_lower for s in skip):
                        deal["website"] = href
    except Exception as e:
        logger.warning(f"Search links error for {name}: {e}")
    return deal


async def fetch_project_page_content(website: str, twitter: str, name: str) -> str:
    """Fetch nội dung từ website chính thức để phân tích"""
    contents = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        if website and website.startswith("http"):
            try:
                r = await client.get(website, headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "meta"]):
                        tag.decompose()
                    text = " ".join(soup.get_text(separator=" ", strip=True).split())
                    contents.append(f"[Nguồn: {website}]\n{text[:4000]}")
            except Exception as e:
                logger.warning(f"Website fetch error: {e}")

        if twitter:
            handle = twitter.rstrip("/").split("/")[-1].lstrip("@")
            if handle and len(handle) > 1 and handle.lower() not in ["twitter.com", "x.com"]:
                for nitter in ["https://nitter.net", "https://nitter.privacydev.net"]:
                    try:
                        r = await client.get(f"{nitter}/{handle}", headers=HEADERS, timeout=10)
                        if r.status_code == 200:
                            soup = BeautifulSoup(r.text, "html.parser")
                            tweets = [t.get_text(strip=True) for t in soup.select(".tweet-content")[:8]]
                            if tweets:
                                contents.append(f"[Nguồn: X/@{handle}]\n" + "\n".join(tweets))
                            break
                    except Exception:
                        continue

    return "\n\n---\n\n".join(contents)


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
        if not all_deals:
            return []
        # Tìm links cho từng dự án
        await asyncio.gather(
            *[search_project_links(client, d) for d in all_deals],
            return_exceptions=True
        )
    logger.info(f"Done: {len(all_deals)} deals")
    return all_deals
