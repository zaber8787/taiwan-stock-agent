# File: crawlers/tick_stream.py
"""
📡 盤中即時 Tick 串流處理器 (Intraday Real-time Tick Streamer)
支援毫秒級接收逐筆成交資料、模擬高頻 Tick 流與即時持倉洗價。
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StockTick:
    """單筆即時成交資料結構 (Tick Data)"""
    ticker: str
    price: float
    volume: int
    timestamp: float                   # epoch timestamp
    time_str: str                      # "HH:MM:SS"
    bid_price: float
    ask_price: float
    is_limit_up: bool = False          # 是否鎖死漲停
    is_limit_down: bool = False        # 是否跌停鎖死

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'price': self.price,
            'volume': self.volume,
            'timestamp': self.timestamp,
            'time_str': self.time_str,
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'is_limit_up': self.is_limit_up,
            'is_limit_down': self.is_limit_down
        }


class TickStreamSimulator:
    """Tick 串流模擬器 (供實盤前測試盤中即時洗價)"""

    def __init__(self, ticker: str, base_price: float):
        self.ticker = ticker.replace('.TW', '')
        self.base_price = base_price
        self.current_price = base_price
        self.limit_up_price = round(base_price * 1.10, 2)
        self.limit_down_price = round(base_price * 0.90, 2)

    def generate_tick(
        self,
        target_price: Optional[float] = None,
        force_limit_up: bool = False,
        force_limit_down: bool = False,
        custom_time_str: Optional[str] = None
    ) -> StockTick:
        """產生單筆即時 Tick"""
        now = time.time()
        time_str = custom_time_str or time.strftime("%H:%M:%S", time.localtime(now))

        if force_limit_up:
            p = self.limit_up_price
            is_lup = True
            is_ldown = False
        elif force_limit_down:
            p = self.limit_down_price
            is_lup = False
            is_ldown = True
        elif target_price is not None:
            p = target_price
            is_lup = (p >= self.limit_up_price)
            is_ldown = (p <= self.limit_down_price)
        else:
            # 隨機微幅波動
            delta = np.random.normal(0, self.base_price * 0.002)
            p = round(self.current_price + delta, 2)
            p = max(self.limit_down_price, min(self.limit_up_price, p))
            is_lup = (p >= self.limit_up_price)
            is_ldown = (p <= self.limit_down_price)

        self.current_price = p
        vol = int(np.random.randint(1, 50))

        return StockTick(
            ticker=self.ticker,
            price=p,
            volume=vol,
            timestamp=now,
            time_str=time_str,
            bid_price=round(p * 0.999, 2),
            ask_price=round(p * 1.001, 2),
            is_limit_up=is_lup,
            is_limit_down=is_ldown
        )
