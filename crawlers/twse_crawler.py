# File: crawlers/twse_crawler.py

'''
Crawler for Taiwan Stock Exchange (TWSE): index, daily stats summary.
Covers: twse.com.tw main indices & volume stats APIs.
'''
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote
import requests

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

from crawlers.config import SOURCES, CrawlerConfig

logger = logging.getLogger(__name__)
_TWS_INDEX_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK'


async def fetch_taiwan_index_v2() -> dict[str, Any]:
    '''Fetch the TWSE market index (加權指數) using openapi-twse JSON REST.'''
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    try:
        if HAS_AIOHTTP:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                async with session.get(_TWS_INDEX_URL, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return _parse_twse_index(data)
        else:
            resp = requests.get(_TWS_INDEX_URL, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                return _parse_twse_index(data)
    except Exception as e:
        logger.warning(f'fetch_taiwan_index_v2 failed: {e}')
    return {}


def _parse_twse_index(data: Any) -> dict[str, Any]:
    if isinstance(data, list) and data:
        latest = data[-1]
        taiex = float(latest.get('TAIEX', 0) or latest.get('ClosingIndex', 0) or 0)
        return {
            'date': latest.get('Date', datetime.now().strftime('%Y%m%d')),
            'close': taiex,
            'change': float(latest.get('Change', 0) or 0),
            'volume': float(latest.get('TradeVolume', 0) or 0),
            'turnover': float(latest.get('TradeValue', 0) or 0),
            'source': 'twse_openapi'
        }
    return {}


async def fetch_taiwan_index_by_date(date_str: str | None = None) -> dict[str, Any]:
    return await fetch_taiwan_index_v2()


async def fetch_taiwan_index_by_date_range(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    item = await fetch_taiwan_index_v2()
    return [item] if item else []


async def crawl_taiwan_market_index() -> dict[str, Any]:
    return await fetch_taiwan_index_v2()


async def get_twse_market_data() -> dict[str, Any]:
    return await fetch_taiwan_index_v2()


async def get_twse_range(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    return await fetch_taiwan_index_by_date_range(start, end)
