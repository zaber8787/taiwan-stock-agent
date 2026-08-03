# File: crawlers/changshang_crawler.py

'''
Industry / Commercial Times (工商時報) newspaper crawler.
Scrapes Taiwan industrial & commercial sector news.
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


async def fetch_changshang_news(query: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    '''Fetch Commercial Times headlines for query or general industrial news.'''
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    url = 'https://ctee.com.tw/category/news/stocks'

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
                        if title and len(title) > 5 and 'ctee.com.tw' in href:
                            if not query or query in title:
                                articles.append({
                                    'title': title,
                                    'url': href,
                                    'source': 'commercial_times',
                                    'published_at': datetime.now().isoformat()
                                })
                                if len(articles) >= limit:
                                    break
        except Exception as e:
            logger.warning(f'Commercial Times fetch failed: {e}')

    return articles


async def crawl_changshang_news(query: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    return await fetch_changshang_news(query=query, limit=limit)


async def crawl_changshang_headlines(limit: int = 20) -> list[dict[str, Any]]:
    return await fetch_changshang_news(query=None, limit=limit)


async def changshang_news_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return await fetch_changshang_news(query=query, limit=top_k)
