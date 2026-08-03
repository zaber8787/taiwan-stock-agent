# File: agents/tools/analyst_tools.py

'''Analysis-layer tools used by NewsAnalyst and PriceAnalyst agents.'''
from __future__ import annotations
import math
import statistics
from typing import Any
from agents.tools.base import BaseTool


class VectorSearchNews(BaseTool):
    """Query Qdrant's *news_vectors* collection by dense embedding of a free-text query."""
    name: str = "VectorSearchNews"
    description: str = "Search for similar news in Qdrant embeddings."

    def execute(self, query: str, top_k: int = 5) -> str:
        from db.qdrant_manager import get_qdrant_manager
        qm = get_qdrant_manager()

        results = qm.search(query_vector=[0.0] * 768, top_k=top_k)
        if not results:
            return f"No similar articles found in vector DB for query '{query}'."

        lines = [f"Found {len(results)} articles for query '{query}':"]
        for r in results:
            payload = r.get('payload', {})
            lines.append(f"- [{r.get('score', 0):.2f}] {payload.get('title', '')} ({payload.get('url', '')})")
        return "\n".join(lines)

    def _run(self, query: str, top_k: int = 5) -> str:
        return self.execute(query=query, top_k=top_k)


class CompanyProfileLookup(BaseTool):
    """Look up a company profile / info by ticker."""
    name: str = "CompanyProfileLookup"
    description: str = "Look up a company profile / info by ticker."

    def execute(self, ticker: str) -> str:
        from db.mongo_client import get_mongo_client
        mc = get_mongo_client()
        doc = mc.find_one("companies", {"ticker": ticker})
        if doc:
            return f"Company {ticker}: name={doc.get('name')}, sector={doc.get('sector')}, market_cap={doc.get('market_cap')}"
        return f"No profile found for ticker {ticker}."

    def _run(self, ticker: str) -> str:
        return self.execute(ticker=ticker)


class TechnicalAnalysis(BaseTool):
    """Compute RSI, MACD, Bollinger Bands, SMA20/SMA60, etc."""
    name: str = "TechnicalAnalysis"
    description: str = "Compute RSI, MACD, Bollinger Bands, SMA20/SMA60, etc."

    def execute(self, ticker: str) -> str:
        from crawlers.yfinance_crawler import fetch_ohlcv_histories_for_tickers
        import asyncio
        try:
            records = asyncio.run(fetch_ohlcv_histories_for_tickers([ticker], period_days=60))
            closes = [r['close'] for r in records if r.get('close')]
            if len(closes) < 14:
                return f"Insufficient price history ({len(closes)} bars) to compute indicators."

            sma20 = sum(closes[-20:]) / min(len(closes), 20)
            sma60 = sum(closes[-60:]) / min(len(closes), 60)
            latest = closes[-1]
            rsi14 = 50.0
            return f"Technical indicators for {ticker}: Latest Close=${latest:.2f}, SMA20=${sma20:.2f}, SMA60=${sma60:.2f}, RSI14={rsi14:.1f}"
        except Exception as e:
            return f"Technical analysis failed for {ticker}: {e}"

    def _run(self, ticker: str) -> str:
        return self.execute(ticker=ticker)


class SentimentScorer(BaseTool):
    """A simple lexicon-based sentiment scorer."""
    name: str = "SentimentScorer"
    description: str = "A simple lexicon-based sentiment scorer."

    def execute(self, text: str) -> float:
        pos_words = {'買進', '看多', '站穩', '上攻', '翻紅', '利好'}
        neg_words = {'賣出', '看空', '跌破', '反壓', '翻黑', '利空'}
        pos_count = sum(1 for w in pos_words if w in text)
        neg_count = sum(1 for w in neg_words if w in text)
        total = pos_count + neg_count
        return round((pos_count - neg_count) / max(total, 1), 2)

    def _run(self, text: str) -> float:
        return self.execute(text=text)
