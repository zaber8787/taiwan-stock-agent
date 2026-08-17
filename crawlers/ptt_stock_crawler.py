# File: crawlers/ptt_stock_crawler.py
"""
PTT Stock board crawler and sentiment analyzer.
"""
from __future__ import annotations
import logging
import html
import re
from typing import Any, List, Dict
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


async def crawl_ptt_stock_board(limit: int = 20) -> List[Dict[str, Any]]:
    """Crawl latest PTT Stock board articles."""
    url = 'https://www.ptt.cc/bbs/Stock/index.html'
    try:
        if HAS_AIOHTTP:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=_HEADERS, connector=connector) as session:
                async with session.get(url, timeout=6) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding='utf-8', errors='ignore')
                        articles = _parse_ptt_articles(text, limit=limit)
                        if articles:
                            return articles
        else:
            resp = requests.get(url, headers=_HEADERS, timeout=6, verify=False)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                articles = _parse_ptt_articles(resp.text, limit=limit)
                if articles:
                    return articles
    except Exception as exc:
        logger.warning(f"PTT crawl error: {exc}")

    return []


def _parse_ptt_articles(html_content: str, limit: int = 20) -> List[Dict[str, Any]]:
    items = []
    matches = re.findall(r'<div class=\"title\">\s*<a href=\"([^\"]+)\">([^<]+)</a>', html_content)
    for href, raw_title in matches[:limit]:
        clean_title = html.unescape(raw_title.strip())
        if clean_title and not clean_title.startswith('[公告]'):
            items.append({
                'title': clean_title,
                'link': 'https://www.ptt.cc' + href,
                'author': 'PTT網友',
                'date': 'today',
                'publisher': 'PTT 股票板'
            })
    return items


async def crawl_ptt_stock_sentiment(stock_code: str) -> Dict[str, Any]:
    """Crawl PTT and calculate sentiment score for a specific stock code."""
    clean_code = stock_code.replace('.TW', '').replace('.TWO', '').strip()
    articles = await crawl_ptt_stock_board(limit=30)
    
    matches = [a for a in articles if clean_code in a.get('title', '')]
    total_posts = len(matches)
    
    pos_keywords = ['多', '噴', '漲', '買', '強', '創高', '利多', '主力']
    neg_keywords = ['空', '跌', '崩', '賣', '弱', '套', '利空', '倒貨']
    
    pos_score = 0
    neg_score = 0
    
    for a in matches:
        title = a.get('title', '')
        pos_score += sum(1 for k in pos_keywords if k in title)
        neg_score += sum(1 for k in neg_keywords if k in title)
        
    total = pos_score + neg_score
    sentiment_score = round((pos_score - neg_score) / max(total, 1), 2) if total > 0 else 0.0
    
    return {
        'stock_code': clean_code,
        'total_posts': total_posts,
        'sentiment_score': sentiment_score,
        'recent_posts': matches[:3]
    }
