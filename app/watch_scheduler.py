# File: app/watch_scheduler.py

'''
Watch Scheduler & Cron Timer Engine for Taiwan Stock Agent.
Manages delayed observation timers (WATCH mode), off-market hour deferrals,
and triggers Phase 2 re-evaluations for Cluster Lag Watching.
'''
from __future__ import annotations
import os
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.market_hours import is_market_open, get_seconds_until_next_market_open
from db.paper_trader import get_paper_trader

logger = logging.getLogger(__name__)

_active_watchlist: list[dict[str, Any]] = []
_instance: WatchScheduler | None = None


class WatchScheduler:
    '''Manages active WATCH mode timers and triggers Phase 2 re-evaluation.'''

    def __init__(self) -> None:
        self.pt = get_paper_trader()

    def register_watch_timer(
        self,
        ticker: str,
        delay_seconds: int = 900, # Default 15 mins
        reason: str = "連動族群補漲觀察",
        tags: list[str] | None = None
    ) -> dict[str, Any]:
        '''
        Register a delayed watch timer for ticker.
        If market is closed (night/weekend), automatically defers timer to next open at 09:05:00.
        '''
        clean_ticker = ticker.replace('.TW', '')
        now = datetime.now()
        deferred = False

        if is_market_open(now):
            target_delay = delay_seconds
        else:
            target_delay = get_seconds_until_next_market_open(now)
            deferred = True
            logger.info(f"⏰ [WatchScheduler] 非開盤時間發布新聞 -> {clean_ticker} 觀察計時器自動改掛至隔日 09:05:00 ({target_delay} 秒後)")

        trigger_time = now + timedelta(seconds=target_delay)

        item = {
            'watch_id': str(uuid.uuid4())[:8],
            'ticker': clean_ticker,
            'reason': reason,
            'tags': tags or [],
            'registered_at': now.isoformat(),
            'trigger_at': trigger_time.isoformat(),
            'remaining_seconds': target_delay,
            'deferred_off_market': deferred,
            'status': 'WATCHING'
        }

        # Check if already watching this ticker to avoid duplicates
        existing = [x for x in _active_watchlist if x['ticker'] == clean_ticker and x['status'] == 'WATCHING']
        if not existing:
            _active_watchlist.append(item)
            # Launch background timer task
            asyncio.create_task(self._timer_worker(item, target_delay))
            logger.info(f"⏱️ [WatchScheduler] 新增排程觀察計時器: {clean_ticker} ({target_delay}s 倒數, 原因: {reason})")

        return item

    async def _timer_worker(self, item: dict[str, Any], delay_seconds: int) -> None:
        '''Worker loop for counting down and executing Phase 2 re-evaluation.'''
        await asyncio.sleep(delay_seconds)
        if item not in _active_watchlist:
            return # Cancelled if cleared
        item['status'] = 'EVALUATING'
        logger.info(f"🔄 [WatchScheduler] 觀察計時到期 -> 觸發 {item['ticker']} 第二階段 Phase 2 補漲確認...")

        # Phase 2 Re-evaluation
        try:
            from agents.decision_maker import synthesize_decision
            signal = synthesize_decision(
                ticker=item['ticker'],
                research_output="Phase 2 re-evaluation",
                news_output=f"排程觀察到期: {item['reason']}"
            )
            side = signal.get('side', 'HOLD')
            confidence = float(signal.get('confidence', 0.5))

            if side in ('BUY', 'SELL') and confidence >= 0.70:
                exec_res = self.pt.execute_signal(signal, current_price=0.0)
                item['status'] = f"EXECUTED_{side}"
                logger.info(f"⚡ [WatchScheduler] Phase 2 補漲確認！自動執行 {side} 下單結果: {exec_res.get('status')}")
            else:
                item['status'] = 'EXPIRED_HOLD'
                logger.info(f"❌ [WatchScheduler] Phase 2 評估未達指標門檻 -> 解除 {item['ticker']} 觀察。")

        except Exception as e:
            logger.warning(f"Phase 2 evaluation error for {item['ticker']}: {e}")
            item['status'] = 'ERROR'

    def get_active_watchlist(self) -> list[dict[str, Any]]:
        '''Return current active watchlist items with updated remaining seconds.'''
        now = datetime.now()
        for item in _active_watchlist:
            if item['status'] == 'WATCHING':
                trig = datetime.fromisoformat(item['trigger_at'])
                rem = int((trig - now).total_seconds())
                item['remaining_seconds'] = max(rem, 0)
        return [x for x in _active_watchlist if x['status'] == 'WATCHING']

    def clear_watchlist(self) -> None:
        '''Clear all active watch timers.'''
        global _active_watchlist
        _active_watchlist.clear()
        logger.info("🧹 [WatchScheduler] 觀察排程清單已完全重置清空。")


def get_watch_scheduler() -> WatchScheduler:
    global _instance
    if _instance is None:
        _instance = WatchScheduler()
    return _instance
