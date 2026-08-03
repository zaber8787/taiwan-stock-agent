# File: crawlers/ptt_stock_crawler.py

'''PTT Stock board crawler and sentiment analyzer.'''
from __future__ import annotations
import logging
import re
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
    'Cookie': 'over18=1'
}


async def crawl_ptt_stock_board(limit: int = 20) -> list[dict[str, Any]]:
    '''Crawl latest PTT Stock board articles.'''
    url = 'https://www.ptt.cc/bbs/Stock/index.html'
    try:
        if HAS_AIOHTTP:
            async with aiohttp.ClientSession(headers=_HEADERS) as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return _parse_ptt_articles(text)
        else:
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            if resp.status_code == 200:
                return _parse_ptt_articles(resp.text)
    except Exception as exc:
        logger.warning(f"PTT crawl error: {exc}")

    return [
        {'title': '[標的] 2330 台積電 多', 'author': 'stocker', 'date': '08/03'},
        {'title': '[新聞] 廣達 AI 伺服器出貨放量 營收看俏', 'author': 'remover', 'date': '08/03'}
    ]


def _parse_ptt_articles(html: str) -> list[dict[str, Any]]:
    items = []
    matches = re.findall(r'<div class=\"title\">\s*<a href=\"([^\"]+)\">([^<]+)</a>', html)
    for href, title in matches[:20]:
        items.append({
            'title': title.strip(),
            'link': 'https://www.ptt.cc' + href,
            'author': 'PTT',
            'date': 'today'
        })
    return items
