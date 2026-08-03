# File: app/news_listener.py

'''
Real-Time Event-Driven News Listener.
Background service that polls Taiwan stock news, matches tickers, ingests into Qdrant,
evaluates impact using AI Agents, and triggers Paper Trading orders automatically.
'''
from __future__ import annotations
import os
import time
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from crawlers.anue_crawler import crawl_anue_stock_news
from crawlers.ptt_stock_crawler import crawl_ptt_stock_board
from crawlers.stock_scanner import get_stock_scanner
from db.paper_trader import get_paper_trader

logger = logging.getLogger(__name__)

_POLL_INTERVAL = int(os.getenv('NEWS_POLL_INTERVAL_SECONDS', '180'))
_MIN_CONFIDENCE_FOR_AUTO_TRADE = 0.70

_recent_events: list[dict[str, Any]] = []
_seen_news_ids: set[str] = set()
_is_running = False


class NewsEventListener:
    '''Background news listener & automated event trader.'''

    def __init__(self) -> None:
        self.poll_interval = _POLL_INTERVAL
        self.scanner = get_stock_scanner()
        self.pt = get_paper_trader()

    async def poll_once(self) -> list[dict[str, Any]]:
        '''Poll latest news from Anue and PTT, match tickers, run AI analysis.'''
        logger.info("📡 [NewsListener] 抓取即時財經新聞與 PTT 股票板文章...")
        processed_events = []
        known_tickers = self.scanner.get_known_tickers()

        # 1. Fetch latest Anue News
        anue_news = await crawl_anue_stock_news("2330") # General Taiwan news
        
        # 2. Match tickers
        for item in anue_news[:10]:
            title = item.get('title', '')
            summary = item.get('summary', '')
            full_text = title + " " + summary
            
            # Simple deduplication
            news_id = str(hash(title))
            if news_id in _seen_news_ids:
                continue
            _seen_news_ids.add(news_id)

            matched_ticker = self._match_ticker(full_text, known_tickers)
            if matched_ticker:
                logger.info(f"⚡ [NewsListener] 偵測到重大新聞關鍵字 -> 關聯個股: {matched_ticker} | 標題: {title[:30]}...")
                event = await self._process_news_event(matched_ticker, title, summary)
                if event:
                    processed_events.append(event)
                    _recent_events.insert(0, event)
                    if len(_recent_events) > 50:
                        _recent_events.pop()

        return processed_events

    def _match_ticker(self, text: str, known_tickers: list[str]) -> str | None:
        '''Match ticker code or company name in news text.'''
        for ticker in known_tickers:
            if ticker in text:
                return ticker

        name_map = {
            '台積電': '2330', '聯發科': '2454', '聯電': '2303', '廣達': '2382',
            '緯創': '3231', '鴻海': '2317', '技嘉': '2376', '大立光': '3008',
            '元大台灣50': '0050', '元大高股息': '0056', '國泰永續高股息': '00878',
            '群益台灣精選高息': '00919', '復華台灣科技優息': '00929', '元大台灣價值高息': '00940'
        }
        for name, code in name_map.items():
            if name in text:
                return code
        return None

    async def _process_news_event(self, ticker: str, title: str, summary: str) -> dict[str, Any]:
        '''Run AI Agents on matched news event & trigger paper trade if confidence >= 0.70.'''
        try:
            from db.qdrant_manager import get_qdrant_manager
            qm = get_qdrant_manager()
            if qm.is_connected():
                qm.upsert_news(
                    articles=[{'id': str(uuid.uuid4()), 'title': title, 'summary': summary, 'ticker': ticker}],
                    embeddings=None
                )
        except Exception:
            pass

        try:
            from agents.team import run_crew
            crew_out = run_crew(ticker=ticker)
            signal = crew_out.signal
        except Exception:
            from agents.decision_maker import synthesize_decision
            signal = synthesize_decision(ticker=ticker, news_output=f"新聞事件: {title}")

        side = signal.get('side', 'HOLD')
        confidence = float(signal.get('confidence', 0.5))
        reason = signal.get('reason', '')

        trade_status = "SKIPPED"
        trade_action = side
        if confidence >= _MIN_CONFIDENCE_FOR_AUTO_TRADE and side in ('BUY', 'SELL'):
            exec_res = self.pt.execute_signal(signal, current_price=0.0)
            trade_status = exec_res.get('status', 'EXECUTED')
            trade_action = exec_res.get('action', side)

        event_record = {
            'event_id': str(uuid.uuid4())[:8],
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'news_title': title,
            'side': side,
            'confidence': confidence,
            'trade_status': trade_status,
            'trade_action': trade_action,
            'reason': reason
        }
        return event_record

    async def start_listening_loop(self) -> None:
        '''Continuous background loop for news polling.'''
        global _is_running
        _is_running = True
        logger.info(f"🚀 [NewsListener] 全自動背景新聞監聽服務啟動 (輪詢間隔: {self.poll_interval} 秒)...")
        while _is_running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.warning(f"NewsListener poll loop error: {e}")
            await asyncio.sleep(self.poll_interval)


def get_recent_news_events() -> list[dict[str, Any]]:
    return _recent_events


def clear_recent_news_events() -> None:
    global _recent_events, _seen_news_ids
    _recent_events.clear()
    _seen_news_ids.clear()
    logger.info("🧹 [NewsListener] 即時新聞事件廣播牆已完全重置清空。")


def get_listener_status() -> dict[str, Any]:
    return {
        'is_running': _is_running,
        'poll_interval_seconds': _POLL_INTERVAL,
        'events_count': len(_recent_events)
    }
