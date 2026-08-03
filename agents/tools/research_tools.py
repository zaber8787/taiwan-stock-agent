# File: agents/tools/research_tools.py

'''Data-fetching tools used by the Researcher / ResearchTask.'''
from __future__ import annotations
from typing import Any
from agents.tools.base import BaseTool


class FetchStockPrices(BaseTool):
    """Pull the latest daily OHLCV record from yfinance / MongoDB."""
    name: str = "FetchStockPrices"
    description: str = "Fetch stock prices"

    def execute(self, ticker: str) -> str:
        from crawlers.yfinance_crawler import fetch_ohlcv_histories_for_tickers
        import asyncio
        try:
            records = asyncio.run(fetch_ohlcv_histories_for_tickers([ticker], period_days=5))
            if records:
                r = records[-1]
                return f"Stock {ticker} on {r['date']}: Close=${r['close']}, Volume={r['volume']}"
            return f"No price data found for {ticker}."
        except Exception as e:
            return f"Error fetching stock prices for {ticker}: {e}"

    def _run(self, ticker: str) -> str:
        return self.execute(ticker=ticker)


class FetchForeignInvestors(BaseTool):
    """Query MOPC foreign-investor holdings per TSEC security code."""
    name: str = "FetchForeignInvestors"
    description: str = "Fetch institutional investors"

    def execute(self, ticker: str) -> str:
        from crawlers.twse_fund_crawler import crawl_institutional_trades
        import asyncio
        try:
            records = asyncio.run(crawl_institutional_trades(stock_code=ticker))
            if records:
                r = records[-1]
                return f"Institutional Trades for {ticker}: ForeignNet={r.get('foreign_net')}, TrustNet={r.get('trust_net')}"
            return f"No institutional data for {ticker}."
        except Exception as e:
            return f"Error fetching institutional trades for {ticker}: {e}"

    def _run(self, ticker: str) -> str:
        return self.execute(ticker=ticker)


class CrawlNewsForIndustry(BaseTool):
    """Scrape a news aggregator for industry-related articles."""
    name: str = "CrawlNewsForIndustry"
    description: str = "Crawl news for industry"

    def execute(self, industry: str, days_back: int = 7) -> str:
        from crawlers.anue_crawler import crawl_anue_for_industry
        import asyncio
        try:
            articles = asyncio.run(crawl_anue_for_industry(industry, limit=5))
            if articles:
                lines = [f"Found {len(articles)} articles for industry '{industry}':"]
                for a in articles:
                    lines.append(f"- {a.get('title')} ({a.get('url')})")
                return "\n".join(lines)
            return f"No news found for industry '{industry}'."
        except Exception as e:
            return f"Error crawling news for industry {industry}: {e}"

    def _run(self, industry: str, days_back: int = 7) -> str:
        return self.execute(industry=industry, days_back=days_back)


class FetchPTTSentiment(BaseTool):
    """Scrape PTT stockboard for mentions of a ticker."""
    name: str = "FetchPTTSentiment"
    description: str = "Fetch PTT sentiment"

    def execute(self, stock: str) -> str:
        from crawlers.ptt_stock_crawler import crawl_ptt_stock_sentiment
        import asyncio
        try:
            res = asyncio.run(crawl_ptt_stock_sentiment(stock_code=stock))
            return f"PTT Sentiment for {stock}: total_posts={res['total_posts']}, score={res['sentiment_score']}"
        except Exception as e:
            return f"Error fetching PTT sentiment for {stock}: {e}"

    def _run(self, stock: str) -> str:
        return self.execute(stock=stock)
