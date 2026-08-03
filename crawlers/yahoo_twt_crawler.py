# File: crawlers/yahoo_twt_crawler.py

'''
Yahoo Finance Taiwan (奇摩股市) dedicated crawler.
Fetches intraday quote metrics and Yahoo TW stock news.
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
YAHOO_BASE = 'https://tw.stock.yahoo.com'


async def fetch_yahoo_intraday_data(ticker: str) -> list[dict[str, Any]]:
    '''Fetch intraday quote data for ticker from Yahoo Finance TW.'''
    url = f'{YAHOO_BASE}/quote/{ticker}'
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    records = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    price_span = soup.find('span', class_='Fz(32px)') or soup.find('span', class_='Fw(b)')
                    price = float(price_span.get_text(strip=True).replace(',', '')) if price_span else 0.0
                    records.append({
                        'ticker': ticker,
                        'price': price,
                        'time': datetime.now().isoformat(),
                        'source': 'yahoo_tw'
                    })
        except Exception as e:
            logger.warning(f'Yahoo TW intraday fetch error for {ticker}: {e}')

    return records


async def fetch_yahoo_news(ticker: str) -> list[dict[str, Any]]:
    '''Fetch news articles specifically for ticker from Yahoo Finance TW.'''
    url = f'{YAHOO_BASE}/quote/{ticker}/news'
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    news = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    for a_tag in soup.find_all('a'):
                        href = a_tag.attrs.get('href', '')
                        title = a_tag.get_text(strip=True)
                        if '/news/' in href and title and len(title) > 5:
                            full_url = href if href.startswith('http') else f'{YAHOO_BASE}{href}'
                            news.append({
                                'title': title,
                                'url': full_url,
                                'published_at': datetime.now().isoformat(),
                                'source': 'yahoo_tw_news'
                            })
        except Exception as e:
            logger.warning(f'Yahoo TW news fetch error for {ticker}: {e}')

    return news


async def crawl_yahoo_twt_for_stock(ticker: str) -> dict[str, Any]:
    '''Aggregate Yahoo TW data for a single stock: prices + news.'''
    prices = await fetch_yahoo_intraday_data(ticker)
    news = await fetch_yahoo_news(ticker)
    return {
        'ticker': ticker,
        'prices': prices,
        'news': news
    }


async def crawl_yahoo_twt_for_multiple(tickers: list[str]) -> dict[str, Any]:
    '''Aggregate data for multiple tickers.'''
    data = {}
    for t in tickers:
        try:
            data[t] = await crawl_yahoo_twt_for_stock(t)
        except Exception as e:
            logger.warning(f'Yahoo TW failed for {t}: {e}')
    return data


async def yahoo_tw_news_search(query: str, limit: int = 15) -> list[dict[str, Any]]:
    '''Search Yahoo Taiwan news for query keyword.'''
    url = f'{YAHOO_BASE}/news?query={quote(query)}'
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    articles = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    for a in soup.find_all('a'):
                        href = a.attrs.get('href', '')
                        title = a.get_text(strip=True)
                        if title and len(title) > 5 and 'news' in href:
                            full_url = href if href.startswith('http') else f'{YAHOO_BASE}{href}'
                            articles.append({
                                'title': title,
                                'source': 'yahoo_tw_news',
                                'url': full_url,
                                'stock_codes': [query],
                                'published_at': datetime.now().isoformat(),
                                'content': ''
                            })
                            if len(articles) >= limit:
                                break
        except Exception as e:
            logger.warning(f'Yahoo TW news search failed for {query}: {e}')

    return articles


async def yahoo_tw_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return await yahoo_tw_news_search(query=query, limit=top_k)
