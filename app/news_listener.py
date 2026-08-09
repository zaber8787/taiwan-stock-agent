# File: app/news_listener.py

'''
Real-Time Event-Driven News Listener with Multi-Stock Support.
Background service that polls Taiwan stock news, extracts related stocks,
runs parallel AI analysis, and triggers paper trading orders automatically.
'''
from __future__ import annotations
import os
import asyncio
import logging
import uuid
import re
from datetime import datetime
from typing import Any
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading

from crawlers.anue_crawler import crawl_anue_stock_news
from crawlers.ptt_stock_crawler import crawl_ptt_stock_board
from crawlers.stock_scanner import get_stock_scanner
from crawlers.industry_graph import TAG_TO_COMPANIES
from db.paper_trader import get_paper_trader

logger = logging.getLogger(__name__)

_POLL_INTERVAL = int(os.getenv('NEWS_POLL_INTERVAL_SECONDS', '180'))
_MAX_PARALLEL_ANALYSIS = int(os.getenv('MAX_PARALLEL_ANALYSIS', '10'))
_ANALYSIS_QUEUE_TIMEOUT = int(os.getenv('ANALYSIS_QUEUE_TIMEOUT', '300'))
_MIN_CONFIDENCE_FOR_AUTO_TRADE = 0.70

_recent_events: list[dict[str, Any]] = []
_seen_news_ids: set[str] = set()
_is_running = False
_analysis_queue: asyncio.Queue | None = None
_executor = ThreadPoolExecutor(max_workers=_MAX_PARALLEL_ANALYSIS)


class AnalysisTask:
    '''Represents a stock analysis task in the queue.'''
    def __init__(self, ticker: str, news_title: str, news_summary: str, timestamp: datetime):
        self.ticker = ticker
        self.news_title = news_title
        self.news_summary = news_summary
        self.timestamp = timestamp
        self.task_id = str(uuid.uuid4())[:8]
        self.status = 'PENDING'
        self.result: dict[str, Any] | None = None
        self.error: str | None = None


class NewsEventListener:
    '''Background news listener & automated event trader with multi-stock support.'''

    def __init__(self) -> None:
        self.poll_interval = _POLL_INTERVAL
        self.scanner = get_stock_scanner()
        self.pt = get_paper_trader()
        self._industry_cache: dict[str, str] = {}
        self._ticker_industry_map: dict[str, str] = {}
        self._build_industry_index()

    def _build_industry_index(self) -> None:
        '''Build industry -> tickers mapping from TAG_TO_COMPANIES.'''
        for tag, companies in TAG_TO_COMPANIES.items():
            for company_info in companies:
                if isinstance(company_info, dict):
                    ticker = company_info.get('code', '')
                    if ticker:
                        self._ticker_industry_map[ticker] = tag
                elif isinstance(company_info, str):
                    # Handle string format "2330 (台積電)"
                    match = re.match(r'(\d{4})', company_info)
                    if match:
                        self._ticker_industry_map[match.group(1)] = tag

    def get_stock_industry(self, ticker: str) -> str | None:
        '''Get industry for a given ticker.'''
        clean_ticker = ticker.replace('.TW', '')
        return self._ticker_industry_map.get(clean_ticker)

    def get_industry_holdings_pct(self, ticker: str) -> float:
        '''Calculate current portfolio percentage for the ticker's industry.'''
        industry = self.get_stock_industry(ticker)
        if not industry:
            return 0.0
        
        pt = get_paper_trader()
        holdings = pt.state.get('holdings', {})
        total_equity = sum(h.get('shares', 0) * h.get('cost_price', 0) for h in holdings.values())
        
        industry_value = 0.0
        for hold_ticker, info in holdings.items():
            if self.get_stock_industry(hold_ticker) == industry:
                industry_value += info.get('shares', 0) * info.get('cost_price', 0)
        
        return industry_value / total_equity if total_equity > 0 else 0.0

    def check_industry_limit(self, ticker: str, proposed_value: float) -> bool:
        '''Check if adding this stock would exceed industry concentration limit.'''
        max_industry_pct = float(os.getenv('MAX_INDUSTRY_PCT', '0.50'))
        current_pct = self.get_industry_holdings_pct(ticker)
        proposed_pct = proposed_value / self.pt.initial_capital if self.pt.initial_capital > 0 else 0
        
        return (current_pct + proposed_pct) <= max_industry_pct

    async def poll_once(self) -> list[dict[str, Any]]:
        '''Poll latest news, extract multiple stocks, run parallel analysis.'''
        logger.info("📡 [NewsListener] 抓取即時財經新聞與 PTT 股票板文章...")
        processed_events = []
        known_tickers = self.scanner.get_known_tickers()

        # Fetch latest news
        anue_news = await crawl_anue_stock_news("")
        
        # Extract and batch process multiple stocks from news
        stock_news_map: dict[str, list[dict]] = defaultdict(list)
        
        for item in anue_news[:20]:
            title = item.get('title', '')
            summary = item.get('summary', '')
            full_text = title + " " + summary
            
            news_id = str(hash(title))
            if news_id in _seen_news_ids:
                continue
            _seen_news_ids.add(news_id)

            # Extract all matched tickers from this news item
            matched_tickers = self._extract_all_tickers(full_text, known_tickers)
            
            if matched_tickers:
                stock_news_map[title].append({
                    'tickers': matched_tickers,
                    'title': title,
                    'summary': summary,
                    'timestamp': datetime.now()
                })

        # Process stocks in parallel with queue management
        for title, news_items in stock_news_map.items():
            for news in news_items:
                for ticker in news['tickers']:
                    task = AnalysisTask(
                        ticker=ticker,
                        news_title=news['title'],
                        news_summary=news['summary'],
                        timestamp=news['timestamp']
                    )
                    event = await self._process_news_task(task)
                    if event:
                        processed_events.append(event)
                        _recent_events.insert(0, event)
                        if len(_recent_events) > 50:
                            _recent_events.pop()

        return processed_events

    def _extract_all_tickers(self, text: str, known_tickers: list[str]) -> list[str]:
        '''Extract all matched tickers from text.'''
        matched = []
        
        # Check known tickers
        for ticker in known_tickers:
            if ticker in text:
                matched.append(ticker)
        
        # Check name mapping
        name_map = {
            '台積電': '2330', '聯發科': '2454', '聯電': '2303', '廣達': '2382',
            '緯創': '3231', '鴻海': '2317', '技嘉': '2376', '大立光': '3008',
            '元大台灣 50': '0050', '元大高股息': '0056', '國泰永續高股息': '00878',
            '群益台灣精選高息': '00919', '復華台灣科技優息': '00929', '元大台灣價值高息': '00940'
        }
        for name, code in name_map.items():
            if name in text and code not in matched:
                matched.append(code)
        
        # Also extract 4-digit stock codes
        code_pattern = re.findall(r'\b(2[0-9]{3}|3[0-9]{3}|00[0-9]{2})\b', text)
        for code in code_pattern:
            if code not in matched and code in known_tickers:
                matched.append(code)
        
        return matched[:5]  # Limit to top 5 stocks per news

    async def _process_news_task(self, task: AnalysisTask) -> dict[str, Any] | None:
        '''Process a single news analysis task with timeout handling.'''
        try:
            logger.info(f"⚡ [NewsListener] 分析新聞關聯個股：{task.ticker} | {task.news_title[:30]}...")
            
            # Run AI analysis with timeout
            signal = await asyncio.wait_for(
                self._run_ai_analysis(task.ticker, task.news_title, task.news_summary),
                timeout=_ANALYSIS_QUEUE_TIMEOUT
            )
            
            task.status = 'COMPLETED'
            task.result = signal
        except asyncio.TimeoutError:
            logger.warning(f"⏰ [NewsListener] 分析超時：{task.ticker}")
            task.status = 'TIMEOUT'
            task.error = 'Analysis timeout'
            signal = {
                'ticker': task.ticker,
                'side': 'HOLD',
                'confidence': 0.0,
                'reason': 'Analysis timeout'
            }
        except Exception as e:
            logger.error(f"❌ [NewsListener] 分析失敗 {task.ticker}: {e}")
            task.status = 'ERROR'
            task.error = str(e)
            signal = {
                'ticker': task.ticker,
                'side': 'HOLD',
                'confidence': 0.0,
                'reason': f'Analysis error: {e}'
            }

        # Execute trade if confidence is high enough
        trade_status = "SKIPPED"
        trade_action = signal.get('side', 'HOLD')
        
        if signal.get('confidence', 0) >= _MIN_CONFIDENCE_FOR_AUTO_TRADE and signal.get('side') in ('BUY', 'SELL'):
            # Check industry limit before buying
            if signal.get('side') == 'BUY':
                estimated_value = self.pt.state['cash'] * float(os.getenv('MAX_SINGLE_STOCK_PCT', '0.20'))
                if not self.check_industry_limit(task.ticker, estimated_value):
                    logger.warning(f"🚫 [NewsListener] 產業集中度限制：{task.ticker}")
                    return None
            
            exec_res = self.pt.execute_signal(signal, current_price=0.0)
            trade_status = exec_res.get('status', 'EXECUTED')
            trade_action = exec_res.get('action', signal.get('side'))

        event_record = {
            'event_id': task.task_id,
            'timestamp': task.timestamp.isoformat(),
            'ticker': task.ticker,
            'news_title': task.news_title,
            'news_summary': task.news_summary,
            'side': signal.get('side', 'HOLD'),
            'confidence': signal.get('confidence', 0.0),
            'trade_status': trade_status,
            'trade_action': trade_action,
            'reason': signal.get('reason', ''),
            'industry': self.get_stock_industry(task.ticker),
            'task_status': task.status
        }
        return event_record

    async def _run_ai_analysis(self, ticker: str, title: str, summary: str) -> dict[str, Any]:
        '''Run AI analysis using crew or fallback.'''
        try:
            from agents.team import run_crew
            crew_out = run_crew(ticker=ticker)
            return crew_out.signal
        except Exception:
            from agents.decision_maker import synthesize_decision
            return synthesize_decision(
                ticker=ticker,
                news_output=f"新聞事件：{title} {summary}"
            )

    async def start_listening_loop(self) -> None:
        '''Continuous background loop for news polling.'''
        global _is_running
        _is_running = True
        logger.info(f"🚀 [NewsListener] 全自動多股票新聞監聽服務啟動 (輪詢間隔：{self.poll_interval} 秒)...")
        while _is_running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.warning(f"NewsListener poll loop error: {e}")
            await asyncio.sleep(self.poll_interval)

    def get_queue_status(self) -> dict[str, Any]:
        '''Get current analysis queue status.'''
        return {
            'max_parallel': _MAX_PARALLEL_ANALYSIS,
            'timeout_seconds': _ANALYSIS_QUEUE_TIMEOUT,
            'recent_events': len(_recent_events),
            'seen_news_count': len(_seen_news_ids)
        }


def get_recent_news_events() -> list[dict[str, Any]]:
    return _recent_events


def clear_recent_news_events() -> None:
    global _recent_events, _seen_news_ids
    _recent_events.clear()
    _seen_news_ids.clear()
    logger.info("🧹 [NewsListener] 即時新聞事件廣播牆已完全重置清空。")


def get_listener_status() -> dict[str, Any]:
    status = {
        'is_running': _is_running,
        'poll_interval_seconds': _POLL_INTERVAL,
        'events_count': len(_recent_events)
    }
    status.update(get_queue_status())
    return status


def get_queue_status() -> dict[str, Any]:
    '''Get analysis queue status.'''
    return {
        'max_parallel': _MAX_PARALLEL_ANALYSIS,
        'timeout_seconds': _ANALYSIS_QUEUE_TIMEOUT,
        'recent_events': len(_recent_events),
        'seen_news_count': len(_seen_news_ids)
    }
