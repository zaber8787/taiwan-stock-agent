# File: crawlers/ecb_newspaper_crawler.py

'''
Economic & Financial newspaper crawler.
Scrapes macro and financial headlines from Taiwan financial press.
'''
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Any
import aiohttp
from bs4 import BeautifulSoup
from crawlers.config import SOURCES, CrawlerConfig

logger = logging.getLogger(__name__)


async def fetch_ecb_news(query: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    '''Fetch financial newspaper headlines for query or general economic news.'''
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    url = 'https://news.cnyes.com/news/category/headline'

    articles = []
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    for a in soup.find_all('a'):
                        title = a.get_text(strip=True)
                        href = a.attrs.get('href', '')
                        if title and len(title) > 5:
                            if not query or query in title:
                                articles.append({
                                    'title': title,
                                    'url': href if href.startswith('http') else f'https://news.cnyes.com{href}',
                                    'source': 'ecb_newspaper',
                                    'published_at': datetime.now().isoformat()
                                })
                                if len(articles) >= limit:
                                    break
        except Exception as e:
            logger.warning(f'ECB Newspaper fetch failed: {e}')

    return articles


async def crawl_ecb_newspaper(query: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    return await fetch_ecb_news(query=query, limit=limit)


async def crawl_ecb_headlines(limit: int = 20) -> list[dict[str, Any]]:
    return await fetch_ecb_news(query=None, limit=limit)


async def ecb_news_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return await fetch_ecb_news(query=query, limit=top_k)
