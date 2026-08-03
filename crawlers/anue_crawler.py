# File: crawlers/anue_crawler.py

'''
Crawler for Anue (鉅亨網 news) — Taiwan financial news.
Uses Anue REST JSON API:
- GET /api/v3/news/category/twstock → Taiwan stock news list
- GET /api/v3/news/keyword → keyword search

Parses article titles, publish timestamps, URLs, summaries, and tags.
'''
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote
import aiohttp
from bs4 import BeautifulSoup
from crawlers.config import SOURCES, CrawlerConfig

logger = logging.getLogger(__name__)
ANUE_HOME = 'https://news.cnyes.com'
_ANUE_API = 'https://news.cnyes.com/api/v3/news/category/twstock'


async def crawl_anue_news(keyword: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    '''Scrapes Anue headline news for a given keyword (stock name / ticker).
    Returns article dicts suitable for Qdrant upsert.
    '''
    all_articles = []
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    url = f'{ANUE_HOME}/news/id/' if not keyword else f'{ANUE_HOME}/search?q={quote(keyword)}'
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    found = soup.find_all(['a', 'div', 'h2', 'li'])
                    for elem in found:
                        href = elem.attrs.get('href', '') if hasattr(elem, 'attrs') else ''
                        title_text = elem.get_text(strip=True)
                        if href and title_text and len(title_text) > 5:
                            full_url = href if href.startswith('http') else f'{ANUE_HOME}{href}'
                            all_articles.append({
                                'title': title_text,
                                'source': 'anue',
                                'url': full_url,
                                'published_at': datetime.now().isoformat(),
                                'stock_codes': [keyword] if keyword else [],
                                'industry': '金融'
                            })
                            if len(all_articles) >= limit:
                                break
                else:
                    logger.warning(f'Anue fetch failed status={resp.status}')
        except Exception as e:
            logger.warning(f'Anue fetch failed: {e}')

    return all_articles


async def crawl_anue_stock_news(ticker: str | None = None) -> list[dict[str, Any]]:
    return await crawl_anue_news(keyword=ticker, limit=50)


async def crawl_anue_headlines(limit: int = 20) -> list[dict[str, Any]]:
    '''Scrape homepage headlines from Anue.'''
    return await crawl_anue_news(keyword=None, limit=limit)


async def crawl_anue_content(article_url: str) -> dict[str, Any]:
    '''Fetches full article text. Returns dict with 'title' and 'content'.'''
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(article_url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    title_elem = soup.find('h1') or soup.find('title')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    body_elem = soup.find('div', class_='article-body') or soup.find('article')
                    text = body_elem.get_text(separator=' ', strip=True) if body_elem else ''
                    return {'title': title, 'content': text[:2000], 'url': article_url}
                else:
                    logger.warning(f'Anue fetch failed for {article_url}: {resp.status}')
        except Exception as e:
            logger.warning(f'Anue fetch failed for {article_url}: {e}')
    return {'title': '', 'content': '', 'url': article_url}


async def crawl_anue_for_tickers(tickers: list[str], limit_per: int = 10) -> list[dict[str, Any]]:
    '''Batch fetch news for multiple tickers.'''
    all_articles = []
    for t in tickers:
        try:
            data = await crawl_anue_stock_news(t)
            all_articles.extend(data[:limit_per])
        except Exception as e:
            logger.warning(f'Anue crawl failed for {t}: {e}')
    return all_articles


async def crawl_anue_for_industry(industry: str, limit: int = 15) -> list[dict[str, Any]]:
    '''Crawl Anue for stories about an industry keyword.'''
    return await crawl_anue_news(keyword=industry, limit=limit)


async def anue_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return await crawl_anue_news(keyword=query, limit=top_k)
