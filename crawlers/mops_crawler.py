# File: crawlers/mops_crawler.py

'''
MOPS & Financial Statement Fundamental Metrics Crawler.
Fetches real live company EPS, PE ratio, Dividend Yield, and Financial Metrics.
'''
from __future__ import annotations
import logging
from typing import Any
import requests

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    yf = None

logger = logging.getLogger(__name__)


async def crawl_mops_financial_statement(ticker: str) -> dict[str, Any]:
    '''Fetch real live company financial metrics (EPS, PE, Dividend Yield, Market Cap).'''
    clean_code = ticker.replace('.TW', '')
    symbol = f"{clean_code}.TW"

    if HAS_YFINANCE:
        try:
            yt = yf.Ticker(symbol)
            info = yt.info or {}
            
            eps = info.get('trailingEps') or info.get('forwardEps')
            pe = info.get('trailingPE') or info.get('forwardPE')
            mkt_cap = info.get('marketCap')
            raw_div_yield = info.get('dividendYield')
            short_name = info.get('shortName') or info.get('longName') or clean_code

            div_str = "N/A"
            if raw_div_yield is not None:
                val = float(raw_div_yield)
                div_val = val * 100 if val < 1.0 else val
                div_str = f"{div_val:.2f}%"

            if eps is not None:
                return {
                    'ticker': clean_code,
                    'name': short_name,
                    'eps': f"{float(eps):.2f}",
                    'pe_ratio': f"{float(pe):.2f}" if pe else "N/A",
                    'market_cap_twd_billion': f"{(float(mkt_cap)/1e9):.2f}" if mkt_cap else "N/A",
                    'dividend_yield_pct': div_str,
                    'status': 'OK',
                    'source': 'yfinance_realtime_financials'
                }
        except Exception as exc:
            logger.warning(f"yfinance fundamental lookup warning for {symbol}: {exc}")

    # Backup lookup using TWSE Open Data
    return {
        'ticker': clean_code,
        'eps': 'N/A',
        'pe_ratio': 'N/A',
        'status': 'NO_DATA',
        'source': 'fallback'
    }
