# File: agents/tools/research_tools.py
"""
Data-fetching tools used by the Researcher / ResearchTask.
All async calls are guarded by run_async_safely to prevent event loop crashes.
"""
from __future__ import annotations
import logging
from typing import Any
from agents.tools.base import BaseTool, run_async_safely

logger = logging.getLogger(__name__)


class FetchStockPrices(BaseTool):
    """Pull the latest daily OHLCV record from yfinance / TWSE."""
    name: str = "FetchStockPrices"
    description: str = "Fetch stock prices and OHLCV history for a ticker (e.g. 3008 or 2330)"

    def execute(self, ticker: str) -> str:
        clean_ticker = str(ticker).replace('.TW', '').replace('.TWO', '').strip()
        from crawlers.yfinance_crawler import fetch_ohlcv_histories_for_tickers
        try:
            records = run_async_safely(fetch_ohlcv_histories_for_tickers([clean_ticker], period_days=5))
            if records:
                r = records[-1]
                return f"Stock {clean_ticker} on {r.get('date', 'recent')}: Close=${r.get('close')}, Volume={r.get('volume')} (High=${r.get('high')}, Low=${r.get('low')})"
            return f"No price data found for {clean_ticker}."
        except Exception as e:
            logger.warning(f"FetchStockPrices error for {clean_ticker}: {e}")
            return f"Error fetching stock prices for {clean_ticker}: {e}"

    def _run(self, ticker: str) -> str:
        return self.execute(ticker=ticker)


class FetchForeignInvestors(BaseTool):
    """Query institutional trades (Foreign, Trust) for a ticker."""
    name: str = "FetchForeignInvestors"
    description: str = "Fetch institutional foreign and investment trust buy/sell records"

    def execute(self, ticker: str) -> str:
        clean_ticker = str(ticker).replace('.TW', '').replace('.TWO', '').strip()
        from crawlers.twse_fund_crawler import crawl_institutional_trades
        try:
            records = run_async_safely(crawl_institutional_trades(stock_code=clean_ticker))
            if records:
                r = records[-1]
                return f"Institutional Trades for {clean_ticker}: ForeignNet={r.get('foreign_net')}, TrustNet={r.get('trust_net')}"
            return f"No institutional data for {clean_ticker}."
        except Exception as e:
            logger.warning(f"FetchForeignInvestors error for {clean_ticker}: {e}")
            return f"Error fetching institutional trades for {clean_ticker}: {e}"

    def _run(self, ticker: str) -> str:
        return self.execute(ticker=ticker)


class CrawlNewsForIndustry(BaseTool):
    """Scrape news for an industry or stock symbol."""
    name: str = "CrawlNewsForIndustry"
    description: str = "Crawl latest news for an industry sector or stock symbol"

    def execute(self, industry: str, days_back: int = 7) -> str:
        from crawlers.anue_crawler import crawl_anue_for_industry
        try:
            articles = run_async_safely(crawl_anue_for_industry(industry, limit=5))
            if articles:
                lines = [f"Found {len(articles)} articles for industry '{industry}':"]
                for a in articles:
                    lines.append(f"- {a.get('title')} ({a.get('url')})")
                return "\n".join(lines)
            return f"No news found for industry '{industry}'."
        except Exception as e:
            logger.warning(f"CrawlNewsForIndustry error: {e}")
            return f"Error crawling news for industry {industry}: {e}"

    def _run(self, industry: str, days_back: int = 7) -> str:
        return self.execute(industry=industry, days_back=days_back)


class FetchPTTSentiment(BaseTool):
    """Scrape PTT stock board for mentions of a ticker."""
    name: str = "FetchPTTSentiment"
    description: str = "Fetch PTT stock sentiment and mentions for a ticker"

    def execute(self, stock: str) -> str:
        clean_stock = str(stock).replace('.TW', '').replace('.TWO', '').strip()
        from crawlers.ptt_stock_crawler import crawl_ptt_stock_sentiment
        try:
            res = run_async_safely(crawl_ptt_stock_sentiment(stock_code=clean_stock))
            return f"PTT Sentiment for {clean_stock}: total_posts={res.get('total_posts', 0)}, score={res.get('sentiment_score', 0.0)}"
        except Exception as e:
            logger.warning(f"FetchPTTSentiment error: {e}")
            return f"Error fetching PTT sentiment for {clean_stock}: {e}"

    def _run(self, stock: str) -> str:
        return self.execute(stock=stock)
