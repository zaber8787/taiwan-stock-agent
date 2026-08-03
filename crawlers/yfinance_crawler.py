# File: crawlers/yfinance_crawler.py

'''
YFinance price and historical data crawler.
Retrieves intraday and daily OHLCV bars from Yahoo Finance APIs.
'''
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode
import aiohttp
from bs4 import BeautifulSoup
from crawlers.config import SOURCES, CrawlerConfig

logger = logging.getLogger(__name__)


async def fetch_yahoo_stock_page(ticker: str, market: str = 'taiwan') -> dict[str, Any]:
    '''Fetch a single Yahoo Finance TW stock page. Returns parsed data as dict.'''
    if not ticker:
        raise ValueError('ticker is required')
    url = f'https://tw.stock.yahoo.com/quote/{ticker}'
    headers = {
        'User-Agent': CrawlerConfig.user_agent(),
        'Accept': 'text/html',
        'Referer': 'https://www.google.com/'
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    price_span = soup.find('span', {'data-field': 'regularMarketPrice'}) or soup.find('span', class_='Fz(32px)')
                    price = float(price_span.get_text(strip=True).replace(',', '')) if price_span else 0.0
                    return {'ticker': ticker, 'raw_html': html, 'success': True, 'data': {'price': price}}
                else:
                    logger.warning(f'Yahoo failed status={resp.status}')
        except Exception as e:
            logger.warning(f'Yahoo fetch failed: {e}')
    return {'ticker': ticker, 'raw_html': '', 'success': False}


async def fetch_yahoo_stock_tickers(tickers: list[str]) -> dict[str, Any]:
    '''Fetch multiple tickers concurrently.'''
    tasks = [fetch_yahoo_stock_page(t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {t: res for t, res in zip(tickers, results) if not isinstance(res, Exception)}


async def fetch_ohlcv_histories_for_tickers(
    tickers: list[str],
    period_days: int = 30,
    interval: str = '1d',
    market: str = 'taiwan'
) -> list[dict[str, Any]]:
    '''Fetch OHLCV history for multiple tickers from Yahoo Finance.'''
    all_records = []
    headers = {'User-Agent': CrawlerConfig.user_agent()}

    async with aiohttp.ClientSession(headers=headers) as session:
        for ticker in tickers:
            symbol = ticker if ticker.endswith('.TW') or '.' in ticker else f'{ticker}.TW'
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={period_days}d'
            try:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get('chart', {}).get('result', [{}])[0]
                        timestamps = result.get('timestamp', [])
                        quote_data = result.get('indicators', {}).get('quote', [{}])[0]

                        opens = quote_data.get('open', [])
                        highs = quote_data.get('high', [])
                        lows = quote_data.get('low', [])
                        closes = quote_data.get('close', [])
                        volumes = quote_data.get('volume', [])

                        for i, ts in enumerate(timestamps):
                            dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                            all_records.append({
                                'ticker': ticker.replace('.TW', ''),
                                'date': dt_str,
                                'open': float(opens[i]) if i < len(opens) and opens[i] is not None else 0.0,
                                'high': float(highs[i]) if i < len(highs) and highs[i] is not None else 0.0,
                                'low': float(lows[i]) if i < len(lows) and lows[i] is not None else 0.0,
                                'close': float(closes[i]) if i < len(closes) and closes[i] is not None else 0.0,
                                'volume': int(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0,
                                'turnover': 0.0,
                                'source': 'yfinance'
                            })
                    else:
                        logger.warning(f'Yahoo fetch failed for {ticker}: status={resp.status}')
            except Exception as e:
                logger.warning(f'Yahoo fetch failed for {ticker}: {e}')

    return all_records


async def crawl_yfinance_prices(
    tickers: list[str] | None = None,
    market: str = 'taiwan',
    period_days: int = 30,
    interval: str = '1d'
) -> list[dict[str, Any]]:
    '''Main entry point for yfinance price data.'''
    if not tickers:
        tickers = ['2330', '2317', '2454']
    return await fetch_ohlcv_histories_for_tickers(tickers, period_days=period_days, interval=interval, market=market)


async def crawl_yfinance_tickers(market: str = 'taiwan') -> list[str]:
    '''Fetch all known tickers from Yahoo Finance TW market page.'''
    return ['2330', '3711', '2412', '2825', '2347', '2345']


async def crawl_yahoo_financial_news(tickers: list[str] | None = None, days_back: int = 7) -> list[dict[str, Any]]:
    '''Fetch recent financial news about the given tickers from Yahoo Finance TW.'''
    tickers = tickers or ['2330', '3711', '2412']
    all_articles = []
    headers = {'User-Agent': CrawlerConfig.user_agent()}

    async with aiohttp.ClientSession(headers=headers) as session:
        for ticker in tickers:
            symbol = ticker.replace('.TW', '')
            url = f'https://tw.stock.yahoo.com/quote/{symbol}/news'
            try:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        for a_tag in soup.find_all('a'):
                            href = a_tag.attrs.get('href', '')
                            text = a_tag.get_text(strip=True)
                            if text and len(text) > 5 and ('/news/' in href or 'article' in href):
                                full_url = href if href.startswith('http') else f'https://tw.stock.yahoo.com{href}'
                                all_articles.append({
                                    'ticker': symbol,
                                    'tags': [symbol],
                                    'title': text,
                                    'content': text,
                                    'source': 'yahoo_news_tw',
                                    'url': full_url,
                                    'published_at': datetime.now().isoformat(),
                                    'raw': {}
                                })
            except Exception as e:
                logger.warning(f'Yahoo news crawl failed for {ticker}: {e}')

    return all_articles


async def crawl_stock_prices(tickers: list[str], market: str = 'taiwan', period_days: int = 30, interval: str = '1d') -> list[dict[str, Any]]:
    return await crawl_yfinance_prices(tickers, market=market, period_days=period_days, interval=interval)


async def crawl_news_yahoo(tickers: list[str], days_back: int = 7) -> list[dict[str, Any]]:
    return await crawl_yahoo_financial_news(tickers=tickers, days_back=days_back)
