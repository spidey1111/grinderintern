import httpx
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
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

ALLOWED_ROUNDS = ["seed", "pre-seed", "preseed", "ico", "ido", "ieo", "private sale", "strategic"]


def is_allowed_round(round_str: str) -> bool:
    if not round_str:
        return True
    r = round_str.lower()
    if re.search(r'series\s+[a-z]', r):
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


async def fetch_rootdata(client: httpx.AsyncClient) -> list[dict]:
    deals = []
    try:
        url = "https://www.rootdata.com/api/funding/list"
        params = {"page": 1, "size": 30}
        r = await client.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", {}).get("list", [])
            for item in items:
                round_type = item.get("roundType", "")
                if not is_allowed_round(round_type):
                    continue
                deals.append({
                    "source": "RootData",
                    "name": item.get("projectName", ""),
                    "amount": item.get("amount", ""),
                    "round": round_type,
                    "investors": item.get("investors", ""),
                    "date": item.get("date", ""),
                    "sector": item.get("category", ""),
                    "description": item.get("description", ""),
                    "website": item.get("website", ""),
                    "twitter": item.get("twitter", ""),
                    "discord": item.get("discord", ""),
                    "token_status": item.get("tokenStatus", ""),
                    "campaigns": [],
                })
    except Exception as e:
        logger.warning(f"RootData fetch error: {e}")
    return deals


async def fetch_cryptorank(client: httpx.AsyncClient) -> list[dict]:
    deals = []
    try:
        url = "https://cryptorank.io/funding-rounds"
        r = await client.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select("table tbody tr")
            for row in rows[:25]:
                cols = row.select("td")
                if len(cols) >= 5:
                    round_type = cols[1].get_text(strip=True)
                    if not is_allowed_round(round_type):
                        continue
                    link_tag = row.select_one("a[href]")
                    project_url = ""
                    if link_tag and "/currencies" in link_tag.get("href", ""):
                        project_url = f"https://cryptorank.io{link_tag['href']}"
                    deals.append({
                        "source": "Cryptorank",
                        "name": cols[0].get_text(strip=True),
                        "amount": cols[2].get_text(strip=True),
                        "round": round_type,
                        "investors": cols[3].get_text(strip=True) if len(cols) > 3 else "",
                        "date": cols[4].get_text(strip=True) if len(cols) > 4 else "",
                        "sector": "",
                        "description": "",
                        "website": "",
                        "twitter": "",
                        "discord": "",
                        "token_status": "",
                        "campaigns": [],
                        "cryptorank_url": project_url,
                    })
    except Exception as e:
        logger.warning(f"Cryptorank fetch error: {e}")
    return deals


async def fetch_cryptorank_detail(client: httpx.AsyncClient, deal: dict) -> dict:
    url = deal.get("cryptorank_url", "")
    if not url:
        return deal
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            tags = soup.select("[class*='tag'], [class*='category'], [class*='badge']")
            if tags:
                deal["sector"] = ", ".join([t.get_text(strip=True) for t in tags[:3]])
            desc_tag = soup.select_one("[class*='description'], [class*='about']")
            if desc_tag:
                deal["description"] = desc_tag.get_text(strip=True)[:400]
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if ("twitter.com" in href or "x.com" in href) and not deal.get("twitter"):
                    deal["twitter"] = href
                elif "discord" in href and not deal.get("discord"):
                    deal["discord"] = href
                elif not deal.get("website") and href.startswith("http") and "cryptorank" not in href and "twitter" not in href and "discord" not in href:
                    deal["website"] = href
    except Exception as e:
        logger.warning(f"Cryptorank detail error for {deal.get('name')}: {e}")
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

    # Fetch website
    website = deal.get("website", "")
    if website:
        try:
            r = await client.get(website, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ", strip=True).lower()
                for kw, label in campaign_keywords.items():
                    if kw in text and label not in campaigns:
                        campaigns.append(label)
        except Exception as e:
            logger.warning(f"Website fetch error for {name}: {e}")

    # Fetch Twitter via Nitter
    twitter = deal.get("twitter", "")
    if twitter:
        handle = twitter.rstrip("/").split("/")[-1].lstrip("@")
        for nitter_host in ["https://nitter.net", "https://nitter.privacydev.net"]:
            try:
                r = await client.get(f"{nitter_host}/{handle}", headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    tweet_text = " ".join([t.get_text(strip=True) for t in soup.select(".tweet-content")[:10]]).lower()
                    for kw, label in campaign_keywords.items():
                        twitter_label = label + " (Twitter)"
                        if kw in tweet_text and twitter_label not in campaigns and label not in campaigns:
                            campaigns.append(twitter_label)
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
        results = await asyncio.gather(
            fetch_rootdata(client),
            fetch_cryptorank(client),
            return_exceptions=True
        )
        all_deals = []
        for result in results:
            if isinstance(result, list):
                all_deals.extend(result)
        all_deals = deduplicate(all_deals)
        logger.info(f"After dedup: {len(all_deals)} deals")

        # Fetch Cryptorank detail pages
        cr_tasks = [fetch_cryptorank_detail(client, d) for d in all_deals if d.get("cryptorank_url")]
        if cr_tasks:
            await asyncio.gather(*cr_tasks, return_exceptions=True)

        # Fetch campaigns
        await asyncio.gather(*[fetch_project_campaigns(client, d) for d in all_deals], return_exceptions=True)

    logger.info(f"Done. Total: {len(all_deals)}")
    return all_deals
