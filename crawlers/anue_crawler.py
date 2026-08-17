# File: crawlers/anue_crawler.py

'''
Anue (鉅亨網) & Live Taiwan Stock News Crawler.
Crawles real-time Taiwan stock news using Google News RSS & Anue Headline REST APIs.
'''
from __future__ import annotations
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote
from typing import Any
import requests

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/xml, application/xml, */*'
}


async def crawl_anue_stock_news(ticker: str) -> list[dict[str, Any]]:
    '''Crawl real-time Taiwan stock news from Google News Taiwan RSS & Anue Headline API.'''
    clean_code = ticker.replace('.TW', '')
    
    # 1. Primary Source: Google News Taiwan RSS for specific ticker
    q = quote(f"{clean_code} 台股")
    gnews_url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    try:
        if HAS_AIOHTTP:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=_HEADERS, connector=connector) as session:
                async with session.get(gnews_url, timeout=6) as resp:
                    if resp.status == 200:
                        xml_bytes = await resp.read()
                        articles = _parse_gnews_xml(xml_bytes, clean_code)
                        if articles:
                            return articles
        else:
            resp = requests.get(gnews_url, headers=_HEADERS, timeout=6, verify=False)
            if resp.status_code == 200:
                articles = _parse_gnews_xml(resp.content, clean_code)
                if articles:
                    return articles
    except Exception as exc:
        logger.warning(f"Google News RSS fetch warning for {clean_code}: {exc}")

    # 2. Secondary Source: Anue CNYES Headline REST API
    anue_url = 'https://news.cnyes.com/api/v3/news/category/headline?limit=15'
    try:
        if HAS_AIOHTTP:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=_HEADERS, connector=connector) as session:
                async with session.get(anue_url, timeout=6) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        articles = _parse_anue_news(data, clean_code)
                        if articles:
                            return articles
        else:
            resp = requests.get(anue_url, headers=_HEADERS, timeout=6, verify=False)
            if resp.status_code == 200:
                articles = _parse_anue_news(resp.json(), clean_code)
                if articles:
                    return articles
    except Exception as exc:
        logger.warning(f"Anue Headline API warning for {clean_code}: {exc}")

    return []


def _parse_gnews_xml(xml_content: bytes, ticker: str) -> list[dict[str, Any]]:
    items = []
    try:
        root = ET.fromstring(xml_content)
        for item in root.findall('.//item')[:15]:
            title = item.find('title').text if item.find('title') is not None else ''
            link = item.find('link').text if item.find('link') is not None else ''
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
            
            # Clean title source format "Title - Publisher"
            publisher = '新聞網'
            if ' - ' in title:
                parts = title.rsplit(' - ', 1)
                title_text = parts[0].strip()
                publisher = parts[1].strip()
            else:
                title_text = title.strip()

            if title_text:
                items.append({
                    'title': title_text,
                    'summary': title_text,
                    'publisher': publisher,
                    'link': link,
                    'published_at': pub_date,
                    'ticker': ticker
                })
    except Exception as e:
        logger.warning(f"Error parsing Google News RSS XML: {e}")
    return items


def _parse_anue_news(data: dict, ticker: str) -> list[dict[str, Any]]:
    items = []
    items_raw = data.get('items', {}).get('data', []) if isinstance(data.get('items'), dict) else []
    for row in items_raw[:15]:
        title = row.get('title', '')
        if title:
            items.append({
                'title': title,
                'summary': row.get('summary', '') or title,
                'publisher': '鉅亨網',
                'link': f"https://news.cnyes.com/news/id/{row.get('newsId')}",
                'published_at': row.get('publishAt', ''),
                'ticker': ticker
            })
    return items


async def crawl_anue_for_industry(industry: str, limit: int = 5) -> list[dict[str, Any]]:
    """Crawl real-time news for an industry sector keyword."""
    return await crawl_anue_stock_news(ticker=industry)
