# File: crawlers/twse_fund_crawler.py

'''
Crawler for TWSE Institutional Investors (三大法人買賣超) data.
Fetches Foreign Investors, Investment Trusts, and Dealers daily trading summaries.
'''
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Any
import aiohttp
from crawlers.config import SOURCES, CrawlerConfig

logger = logging.getLogger(__name__)
TWSE_FUND_URL = 'https://www.twse.com.tw/rwd/zh/fund/T86'


async def fetch_twse_institutional_investors(date_str: str | None = None) -> list[dict[str, Any]]:
    '''Fetch TWSE institutional trading data by date (YYYYMMDD).'''
    date_str = date_str or datetime.now().strftime('%Y%m%d')
    url = f'{TWSE_FUND_URL}?date={date_str}&selectType=ALLBUT0999&response=json'
    headers = {'User-Agent': CrawlerConfig.user_agent()}

    records = []
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('stat') == 'OK' and 'data' in data:
                        for row in data['data']:
                            if len(row) >= 11:
                                records.append({
                                    'ticker': row[0].strip(),
                                    'name': row[1].strip(),
                                    'foreign_buy': row[2].strip(),
                                    'foreign_sell': row[3].strip(),
                                    'foreign_net': row[4].strip(),
                                    'trust_net': row[7].strip() if len(row) > 7 else '0',
                                    'dealer_net': row[10].strip() if len(row) > 10 else '0',
                                    'date': date_str,
                                    'source': 'twse_fund'
                                })
        except Exception as e:
            logger.warning(f'TWSE Fund fetch failed for {date_str}: {e}')

    return records


async def fetch_institutional_investors_by_range(start: str, end: str) -> list[dict[str, Any]]:
    '''Fetch institutional trading records across a date range.'''
    rec = await fetch_twse_institutional_investors(start)
    return rec


async def crawl_twse_fund(date_str: str | None = None) -> list[dict[str, Any]]:
    return await fetch_twse_institutional_investors(date_str=date_str)


async def crawl_institutional_trades(stock_code: str | None = None) -> list[dict[str, Any]]:
    records = await fetch_twse_institutional_investors()
    if stock_code:
        return [r for r in records if r['ticker'] == stock_code]
    return records
