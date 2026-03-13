import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}


async def fetch_rootdata(client: httpx.AsyncClient) -> list[dict]:
    """Fetch recent funding from RootData API (public endpoint)"""
    deals = []
    try:
        url = "https://www.rootdata.com/api/funding/list"
        params = {"page": 1, "size": 20}
        r = await client.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", {}).get("list", [])
            for item in items:
                deals.append({
                    "source": "RootData",
                    "name": item.get("projectName", ""),
                    "amount": item.get("amount", ""),
                    "round": item.get("roundType", ""),
                    "investors": item.get("investors", ""),
                    "date": item.get("date", ""),
                    "sector": item.get("category", ""),
                    "description": item.get("description", ""),
                    "website": item.get("website", ""),
                    "twitter": item.get("twitter", ""),
                    "token_status": item.get("tokenStatus", ""),
                    "stage": item.get("stage", ""),
                })
    except Exception as e:
        logger.warning(f"RootData fetch error: {e}")
    return deals


async def fetch_cryptorank(client: httpx.AsyncClient) -> list[dict]:
    """Fetch from Cryptorank fundraising page"""
    deals = []
    try:
        url = "https://cryptorank.io/funding-rounds"
        r = await client.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select("table tbody tr")
            for row in rows[:15]:
                cols = row.select("td")
                if len(cols) >= 5:
                    deals.append({
                        "source": "Cryptorank",
                        "name": cols[0].get_text(strip=True),
                        "amount": cols[2].get_text(strip=True),
                        "round": cols[1].get_text(strip=True),
                        "investors": cols[3].get_text(strip=True),
                        "date": cols[4].get_text(strip=True),
                        "sector": "",
                        "description": "",
                        "website": "",
                        "twitter": "",
                        "token_status": "",
                        "stage": "",
                    })
    except Exception as e:
        logger.warning(f"Cryptorank fetch error: {e}")
    return deals


async def fetch_theblock(client: httpx.AsyncClient) -> list[dict]:
    """Fetch from The Block funding news RSS/API"""
    deals = []
    try:
        url = "https://www.theblock.co/rss/funding"
        r = await client.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item")[:10]
            for item in items:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                description = item.find("description")
                deals.append({
                    "source": "TheBlock",
                    "name": title.get_text(strip=True) if title else "",
                    "amount": "",
                    "round": "",
                    "investors": "",
                    "date": pub_date.get_text(strip=True) if pub_date else "",
                    "sector": "",
                    "description": description.get_text(strip=True)[:300] if description else "",
                    "website": link.get_text(strip=True) if link else "",
                    "twitter": "",
                    "token_status": "",
                    "stage": "",
                })
    except Exception as e:
        logger.warning(f"TheBlock fetch error: {e}")
    return deals


async def fetch_dlnews(client: httpx.AsyncClient) -> list[dict]:
    """Fetch from DLNews funding section"""
    deals = []
    try:
        url = "https://www.dlnews.com/articles/defi/"
        r = await client.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            articles = soup.select("article")[:8]
            for article in articles:
                title_tag = article.select_one("h2, h3")
                link_tag = article.select_one("a")
                if title_tag and ("raise" in title_tag.text.lower() or "funding" in title_tag.text.lower() or "million" in title_tag.text.lower()):
                    deals.append({
                        "source": "DLNews",
                        "name": title_tag.get_text(strip=True),
                        "amount": "",
                        "round": "",
                        "investors": "",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "sector": "",
                        "description": title_tag.get_text(strip=True),
                        "website": f"https://www.dlnews.com{link_tag['href']}" if link_tag and link_tag.get('href') else "",
                        "twitter": "",
                        "token_status": "",
                        "stage": "",
                    })
    except Exception as e:
        logger.warning(f"DLNews fetch error: {e}")
    return deals


def deduplicate(deals: list[dict]) -> list[dict]:
    """Remove duplicate projects by name"""
    seen = set()
    unique = []
    for deal in deals:
        name = deal.get("name", "").lower().strip()
        if name and name not in seen:
            seen.add(name)
            unique.append(deal)
    return unique


async def fetch_funding_news() -> list[dict]:
    """Main function: fetch from all sources concurrently"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(
            fetch_rootdata(client),
            fetch_cryptorank(client),
            fetch_theblock(client),
            fetch_dlnews(client),
            return_exceptions=True
        )

    all_deals = []
    for result in results:
        if isinstance(result, list):
            all_deals.extend(result)
        else:
            logger.warning(f"Source returned exception: {result}")

    all_deals = deduplicate(all_deals)
    logger.info(f"Total deals fetched: {len(all_deals)}")
    return all_deals
