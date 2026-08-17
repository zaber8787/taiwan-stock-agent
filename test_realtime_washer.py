#!/usr/bin/env python3
"""
🌊 盤中即時 Tick 洗價與當沖停損/移動停利測試腳本
"""
import os
import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from crawlers.tick_stream import TickStreamSimulator, StockTick
from app.realtime_washer import RealtimePositionWasher
from db.paper_trader import get_paper_trader


def test_realtime_washer_flow():
    print("=" * 70)
    print("🌊 測試盤中即時 Tick 洗價 (破位當沖停損 / 移動停利 / 鎖漲停跟單)")
    print("=" * 70)

    pt = get_paper_trader()
    pt.reset_account(capital=1000000.0)

    # 1. 建立初始買入持倉 (買進 2330, 成本 100 元)
    pt.execute_signal({'ticker': '2330', 'side': 'BUY', 'confidence': 1.0, 'reason': '策略進場測試'}, current_price=100.0)
    washer = RealtimePositionWasher()
    sim = TickStreamSimulator('2330', base_price=100.0)

    # 2. 情境 A: 股價上漲至 +12% (112元) 激活移動停利，隨後回檔至 109元 (回檔 2.68% >= 2%)
    print("\n[情境 A: +10% 激活動態移動停利，自高點回檔 2% 平倉]")
    # Tick 1: 衝高至 112
    tick_high = sim.generate_tick(target_price=112.0, custom_time_str="10:15:00")
    res1 = washer.process_tick(tick_high)
    print(f"  價格達 ${tick_high.price} (+12%) ➔ 移動停利狀態: 已激活 ({washer.trailing_activated.get('2330')})")
    assert washer.trailing_activated.get('2330') is True

    # Tick 2: 回檔至 109 (自 112 回檔 2.68%)
    tick_drop = sim.generate_tick(target_price=109.0, custom_time_str="10:30:00")
    res2 = washer.process_tick(tick_drop)
    print(f"  價格回檔至 ${tick_drop.price} ➔ 洗價觸發動作: {res2.get('action') if res2 else None}")
    assert res2 is not None and res2['action'] == 'TAKE_PROFIT_EXECUTED'
    print(f"  實現損益: ${res2['trade']['realized_pnl']:+,.2f} ({res2['trade']['roi_pct']:+.2f}%)")

    # 3. 情境 B: 再次買入，隨後盤中急殺至 -6.5% (93.5元) 觸發當沖強制停損平倉 (享0.15%降稅)
    print("\n[情境 B: 盤中走勢急殺至 -6% 剛性停損，自動觸發當沖降稅平倉]")
    pt.execute_signal({'ticker': '2330', 'side': 'BUY', 'confidence': 1.0, 'reason': '進場測試停損'}, current_price=100.0)
    
    tick_crash = sim.generate_tick(target_price=93.5, custom_time_str="11:10:00") # -6.5%
    res3 = washer.process_tick(tick_crash)
    print(f"  價格破位至 ${tick_crash.price} (-6.5%) ➔ 洗價觸發動作: {res3.get('action') if res3 else None}")
    assert res3 is not None and res3['action'] == 'STOP_LOSS_EXECUTED'
    print(f"  實現損益: ${res3['trade']['realized_pnl']:+,.2f} ({res3['trade']['roi_pct']:+.2f}%)")

    # 4. 情境 C: 09:30 前鎖死漲停跟單監聽
    print("\n[情境 C: 09:30 前強勢鎖死漲停監聽]")
    tick_lup = sim.generate_tick(force_limit_up=True, custom_time_str="09:12:00")
    res4 = washer.process_tick(tick_lup)
    print(f"  漲停時間 {tick_lup.time_str} ➔ 監聽動作: {res4.get('action') if res4 else None}")
    assert res4 is not None and res4['action'] == 'LIMIT_UP_WATCH'
    print(f"  預警通報: {res4.get('message')}")

    print("\n" + "=" * 70)
    print("✅ 盤中即時 Tick 洗價與風控守護測試全部 100% 通過！")
    print("=" * 70)


if __name__ == '__main__':
    test_realtime_washer_flow()
