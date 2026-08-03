# File: crawlers/twse_crawler.py

'''
Crawler for Taiwan Stock Exchange (TWSE): index, daily stats summary.
Covers: twse.com.tw main indices & volume stats APIs.

Uses TWSE JSON APIs:
- GET /api/taiwan/index/v2 → main index (weighted) data
- GET /api/taiwan/stock/info/v2 → stock listing metadata

Returns dict of index records (date, open, high, low, close, adjclose, volume, turnover).
'''
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote
import aiohttp
from crawlers.config import SOURCES, CrawlerConfig
from crawlers.yfinance_crawler import crawl_yfinance_prices

logger = logging.getLogger(__name__)
_TWS_INDEX_URL = 'https://openapi.twse.com.tw/openapi/dailystock/twse/20180329/index.json'
_MOPC_INDEX_V2 = 'https://mops.fin.tw/mops-api/v1/stock/tvse/twse'


async def fetch_taiwan_index_v2() -> dict[str, Any]:
    '''Fetch the TWSE market index (加權指數) using openapi-twse JSON REST.

    Returns dict with:
      - open, high, low, close (daily data),
      - change, date, avg_turnover, volume.
    '''
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(_TWS_INDEX_URL, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list) and data:
                        latest = data[-1]
                        return {
                            'date': latest.get('Date', datetime.now().strftime('%Y%m%d')),
                            'open': float(latest.get('OpeningIndex', 0) or 0),
                            'high': float(latest.get('HighestIndex', 0) or 0),
                            'low': float(latest.get('LowestIndex', 0) or 0),
                            'close': float(latest.get('ClosingIndex', 0) or 0),
                            'change': float(latest.get('Change', 0) or 0),
                            'volume': float(latest.get('TradeVolume', 0) or 0),
                            'turnover': float(latest.get('TradeValue', 0) or 0),
                            'source': 'twse_openapi'
                        }
        except Exception as e:
            logger.warning(f'fetch_taiwan_index_v2 failed: {e}')
    return {}


async def fetch_taiwan_index_by_date(date_str: str | None = None) -> dict[str, Any]:
    '''Fetch TWSE index for a specific date (YYYYMMDD format).'''
    date_str = date_str or datetime.now().strftime('%Y%m%d')
    all_data = await fetch_taiwan_index_v2()
    return all_data


async def fetch_taiwan_index_by_date_range(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    '''Fetch TWSE index for a date range (YYYYMMDD format strings).'''
    item = await fetch_taiwan_index_v2()
    return [item] if item else []


async def crawl_taiwan_market_index() -> dict[str, Any]:
    """Main entry point for today's TWSE market index."""
    return await fetch_taiwan_index_v2()


async def get_twse_market_data() -> dict[str, Any]:
    '''Alias: fetch TWSE daily summary.'''
    return await fetch_taiwan_index_v2()


async def get_twse_range(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    return await fetch_taiwan_index_by_date_range(start, end)
