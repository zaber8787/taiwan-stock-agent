# File: crawlers/yfinance_crawler.py
"""
Yahoo Finance crawler for intraday quotes and historical OHLCV data.
Supports both TWSE (.TW) and TPEx (.TWO) securities.
"""
from __future__ import annotations
import logging
from typing import Any, List, Optional
import requests

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    yf = None

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


async def fetch_yahoo_stock_page(ticker: str) -> dict[str, Any]:
    """Fetch live stock quote from Yahoo Finance TW web page."""
    clean_code = ticker.replace('.TW', '').replace('.TWO', '').strip()
    url = f'https://tw.stock.yahoo.com/quote/{clean_code}'
    try:
        if HAS_AIOHTTP:
            async with aiohttp.ClientSession(headers=_HEADERS) as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        price = _extract_price_from_html(text)
                        if price and price > 0:
                            return {'success': True, 'data': {'ticker': clean_code, 'price': price}}
        else:
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            if resp.status_code == 200:
                price = _extract_price_from_html(resp.text)
                if price and price > 0:
                    return {'success': True, 'data': {'ticker': clean_code, 'price': price}}
    except Exception as exc:
        logger.warning(f"Yahoo page fetch error for {clean_code}: {exc}")

    return {'success': False, 'data': {'ticker': clean_code, 'price': 0.0}}


def _extract_price_from_html(html: str) -> Optional[float]:
    """Regex parsing for stock price in Yahoo HTML."""
    import re
    match = re.search(r'\"Fz\(32px\)[^\"]*\">([\d\.,]+)</span>', html)
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            pass
    return None


async def fetch_ohlcv_histories_for_tickers(
    tickers: List[str],
    period: str = '5d',
    period_days: Optional[int] = None
) -> List[dict[str, Any]]:
    """
    Fetch historical OHLCV data for given tickers.
    Supports period strings ('5d', '1mo', '3mo') or integer period_days.
    """
    if period_days:
        period_str = f"{period_days}d" if period_days <= 90 else "3mo"
    else:
        period_str = period

    results = []
    for t in tickers:
        clean = t.replace('.TW', '').replace('.TWO', '').strip()
        found = False
        if HAS_YFINANCE:
            for suffix in ['.TW', '.TWO']:
                sym = f"{clean}{suffix}"
                try:
                    tk = yf.Ticker(sym)
                    df = tk.history(period=period_str)
                    if not df.empty and len(df) > 0:
                        for idx, row in df.iterrows():
                            date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
                            results.append({
                                'ticker': clean,
                                'date': date_str,
                                'close': float(row['Close']),
                                'open': float(row['Open']),
                                'high': float(row['High']),
                                'low': float(row['Low']),
                                'volume': int(row['Volume'])
                            })
                        found = True
                        break
                except Exception as e:
                    logger.debug(f"yfinance lookup {sym} failed: {e}")

    return results


async def crawl_yfinance_prices(ticker: str) -> List[dict[str, Any]]:
    """Alias for fetching OHLCV price histories for a single ticker."""
    return await fetch_ohlcv_histories_for_tickers([ticker])
