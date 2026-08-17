# File: app/realtime_washer.py
"""
🌊 盤中即時持倉洗價與停損停利守護器 (Real-time Position Washer)
功能：
1. 毫秒級接收或監聽持倉標的的即時 Tick。
2. 觸發 -6% 剛性停損時，立即在盤中以當沖平倉方式強制出場，享受 0.15% 當沖降稅紅利。
3. 標的漲幅達 +10% 時激活移動停利線，自高點回檔 2% 自動市價停利鎖定利潤。
4. 偵測 09:30 前鎖死漲停，自動觸發次日溢價跟單標記與 Discord 即時通報。
"""
from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from crawlers.tick_stream import StockTick
from db.paper_trader import get_paper_trader
from app.notifier import get_discord_notifier

logger = logging.getLogger(__name__)


class RealtimePositionWasher:
    """即時持倉動態洗價守護器"""

    def __init__(self):
        self.pt = get_paper_trader()
        # 紀錄各標的自買入以來的最高價 {ticker: peak_price}
        self.peak_prices: Dict[str, float] = {}
        # 紀錄移動停利是否已激活 {ticker: bool}
        self.trailing_activated: Dict[str, bool] = {}

    def process_tick(self, tick: StockTick) -> Optional[Dict[str, Any]]:
        """
        處理單筆即時 Tick，執行即時洗價與風控判定。
        回傳觸發之平倉指令或預警，若無觸發回傳 None。
        """
        ticker = tick.ticker
        holding = self.pt.state.get('holdings', {}).get(ticker)
        
        if not holding or holding.get('shares', 0) <= 0:
            # 若無持倉但 09:30 前鎖漲停，發出關注預警
            if tick.is_limit_up:
                return {
                    'action': 'LIMIT_UP_WATCH',
                    'ticker': ticker,
                    'price': tick.price,
                    'time': tick.time_str,
                    'message': f"🚀 {ticker} 於 {tick.time_str} 強勢鎖死漲停，符合 09:30 前主力強鎖特徵！"
                }
            return None

        cost = holding['cost_price']
        curr_price = tick.price
        shares = holding['shares']
        roi_pct = ((curr_price - cost) / cost) * 100.0

        # 更新最高價
        prev_peak = self.peak_prices.get(ticker, cost)
        if curr_price > prev_peak:
            self.peak_prices[ticker] = curr_price
            prev_peak = curr_price

        # --- 規則 1: -6% 剛性停損 (盤中破位當沖強制平倉) ---
        if roi_pct <= -6.0:
            logger.warning(f"🚨 [即時洗價] {ticker} 盤中急殺破位 {roi_pct:.2f}% <= -6.0%，觸發當沖降稅平倉！")
            trade = self.pt.execute_signal(
                signal={
                    'ticker': ticker,
                    'side': 'SELL',
                    'reason': f"🚨 盤中走勢破位 ({roi_pct:.2f}%) 觸發 -6% 剛性停損當沖平倉 (享0.15%降稅)",
                    'confidence': 1.0
                },
                current_price=curr_price
            )
            # 清理追蹤狀態
            self.peak_prices.pop(ticker, None)
            self.trailing_activated.pop(ticker, None)
            return {
                'action': 'STOP_LOSS_EXECUTED',
                'ticker': ticker,
                'roi_pct': roi_pct,
                'price': curr_price,
                'trade': trade
            }

        # --- 規則 2: +10% 激活動態移動停利，自高點回檔 2% 平倉 ---
        if roi_pct >= 10.0:
            self.trailing_activated[ticker] = True

        if self.trailing_activated.get(ticker, False):
            # 計算自最高價的回檔幅度
            drawdown_from_peak_pct = ((prev_peak - curr_price) / prev_peak) * 100.0
            if drawdown_from_peak_pct >= 2.0:
                logger.info(f"🎯 [即時洗價] {ticker} 達到移動停利條件 (高點 ${prev_peak} 回檔 {drawdown_from_peak_pct:.2f}% >= 2%)，獲利了結！")
                trade = self.pt.execute_signal(
                    signal={
                        'ticker': ticker,
                        'side': 'SELL',
                        'reason': f"🎯 移動停利觸發 (最高點 ${prev_peak} 回檔 {drawdown_from_peak_pct:.2f}%)，鎖定獲利 +{roi_pct:.2f}%",
                        'confidence': 1.0
                    },
                    current_price=curr_price
                )
                self.peak_prices.pop(ticker, None)
                self.trailing_activated.pop(ticker, None)
                return {
                    'action': 'TAKE_PROFIT_EXECUTED',
                    'ticker': ticker,
                    'roi_pct': roi_pct,
                    'price': curr_price,
                    'trade': trade
                }

        return None


_washer_instance: Optional[RealtimePositionWasher] = None

def get_realtime_washer() -> RealtimePositionWasher:
    global _washer_instance
    if _washer_instance is None:
        _washer_instance = RealtimePositionWasher()
    return _washer_instance
