# File: crawlers/ptt_stock_crawler.py

'''
Crawler for PTT Stock Board (批踢踢實業坊 Stock 板).
Scrapes article headers, titles, push counts, and computes community sentiment.
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
PTT_STOCK_URL = 'https://www.ptt.cc/bbs/Stock/index.html'


async def fetch_ptt_stock_posts(pages: int = 3) -> list[dict[str, Any]]:
    '''Scrape PTT Stock board articles across the specified number of pages.'''
    posts = []
    headers = {'User-Agent': CrawlerConfig.user_agent()}
    cookies = {'over18': '1'}
    url = PTT_STOCK_URL

    async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
        for _ in range(pages):
            try:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        rows = soup.find_all('div', class_='r-ent')
                        for row in rows:
                            title_div = row.find('div', class_='title')
                            nrec_div = row.find('div', class_='nrec')
                            author_div = row.find('div', class_='author')
                            if title_div and title_div.find('a'):
                                a_tag = title_div.find('a')
                                title = a_tag.get_text(strip=True)
                                href = a_tag.attrs.get('href', '')
                                push_count = nrec_div.get_text(strip=True) if nrec_div else '0'
                                author = author_div.get_text(strip=True) if author_div else ''
                                posts.append({
                                    'title': title,
                                    'url': f'https://www.ptt.cc{href}',
                                    'push_count': push_count,
                                    'author': author,
                                    'published_at': datetime.now().isoformat()
                                })
                        prev_link = soup.find('a', string='‹ 上頁')
                        if prev_link and 'href' in prev_link.attrs:
                            url = f"https://www.ptt.cc{prev_link['href']}"
                        else:
                            break
                    else:
                        break
            except Exception as e:
                logger.warning(f'PTT fetch error: {e}')
                break

    return posts


async def crawl_ptt_stock_sentiment(stock_code: str | None = None) -> dict[str, Any]:
    '''Calculate PTT sentiment score and metrics for stock_code.'''
    posts = await fetch_ptt_stock_posts(pages=3)
    matched = [p for p in posts if not stock_code or stock_code in p['title']]
    
    pos_words = {'多', '看多', '買進', '漲', '飛', '噴', '站穩', '大利多'}
    neg_words = {'空', '看空', '賣出', '跌', '崩', '慘', '跌破', '大利空'}
    
    pos_count = 0
    neg_count = 0
    for p in matched:
        t = p['title']
        if any(w in t for w in pos_words):
            pos_count += 1
        if any(w in t for w in neg_words):
            neg_count += 1

    total = len(matched)
    score = (pos_count - neg_count) / max(total, 1)
    return {
        'stock_code': stock_code,
        'total_posts': total,
        'positive_posts': pos_count,
        'negative_posts': neg_count,
        'sentiment_score': round(score, 2),
        'recent_posts': matched[:5]
    }


async def crawl_ptt_posts(pages: int = 3) -> list[dict[str, Any]]:
    return await fetch_ptt_stock_posts(pages=pages)


async def crawl_ptt_stock(stock_code: str | None = None) -> dict[str, Any]:
    return await crawl_ptt_stock_sentiment(stock_code=stock_code)
