# File: crawlers/mops_crawler.py

'''
Crawler for Market Observation Post System (MOPS / 公開資訊觀測站).
Fetches financial statements (revenue, EPS) and material announcements.
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
MOPS_BASE_URL = 'https://mops.twse.com.tw/mops/web'


async def fetch_mops_financial_statement(company_code: str, year: int = 2026, season: int = 1) -> dict[str, Any]:
    '''Fetch MOPS financial statement metrics (EPS, revenue) for company.'''
    url = f'{MOPS_BASE_URL}/t163sb01'
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    payload = {
        'encode_req': '1',
        'step': '1',
        'firstin': '1',
        'co_id': company_code,
        'year': str(year),
        'season': str(season)
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.post(url, data=payload, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    return {
                        'company_code': company_code,
                        'year': year,
                        'season': season,
                        'raw_html': html[:5000],
                        'source': 'mops'
                    }
        except Exception as e:
            logger.warning(f'MOPS statement fetch error for {company_code}: {e}')

    return {'company_code': company_code, 'year': year, 'season': season, 'source': 'mops'}


async def fetch_mops_material_information(company_code: str) -> list[dict[str, Any]]:
    '''Fetch recent material announcements (重大訊息) for company_code.'''
    url = f'{MOPS_BASE_URL}/t05st01'
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    payload = {
        'encode_req': '1',
        'step': '1',
        'firstin': '1',
        'co_id': company_code
    }

    announcements = []
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.post(url, data=payload, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    for row in soup.find_all('tr'):
                        tds = row.find_all('td')
                        if len(tds) >= 4:
                            announcements.append({
                                'company_code': company_code,
                                'date': tds[0].get_text(strip=True),
                                'time': tds[1].get_text(strip=True),
                                'subject': tds[4].get_text(strip=True) if len(tds) > 4 else tds[2].get_text(strip=True),
                                'source': 'mops_material_info'
                            })
        except Exception as e:
            logger.warning(f'MOPS material info fetch error for {company_code}: {e}')

    return announcements


async def crawl_mops_data(company_code: str) -> dict[str, Any]:
    stmt = await fetch_mops_financial_statement(company_code)
    announcements = await fetch_mops_material_information(company_code)
    return {
        'company_code': company_code,
        'financial_statement': stmt,
        'material_info': announcements
    }


async def crawl_mops_announcements(company_code: str) -> list[dict[str, Any]]:
    return await fetch_mops_material_information(company_code)
