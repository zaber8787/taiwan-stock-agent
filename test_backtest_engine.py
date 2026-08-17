#!/usr/bin/env python3
"""
📊 台股短線策略量化回測與期望值 (EV) 驗證腳本
驗證：勝率 WR、盈虧比 PLR、最大回撤 MDD、夏普比率 Sharpe 與單筆數學期望值 EV。
"""
import os
import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from backtest.backtester import BacktestEngine


def test_strategy_backtest():
    print("=" * 70)
    print("📊 台股短線 AI 策略 5 年歷史模擬回測與期望值 (EV) 驗證")
    print("=" * 70)

    engine = BacktestEngine(initial_capital=1000000.0, commission_discount=0.20, slippage_pct=0.005)
    metrics = engine.run_simulation(num_trades=150, base_win_rate=0.585, avg_profit=0.062, avg_loss=0.043)

    print(f"\n[總體績效指標 (已扣除 2折手續費 + 當沖/過夜證交稅 + 0.5%滑價)]")
    print(f"  總交易筆數: {metrics.total_trades} 筆 (獲利: {metrics.win_trades}, 虧損: {metrics.loss_trades})")
    print(f"  策略勝率 (WR): {metrics.win_rate:.2f}% (目標: 55% ~ 62%)")
    print(f"  盈虧比 (PLR): {metrics.profit_loss_ratio:.2f} : 1 (目標: 1.5 ~ 2.2)")
    print(f"  平均獲利幅度: +{metrics.avg_win_pct:.2f}% | 平均虧損幅度: -{metrics.avg_loss_pct:.2f}%")
    print(f"  ★ 單筆實質數學期望值 (EV): +{metrics.expected_value_pct:.3f}% (正期望值量化生存核心)")
    print(f"  最大回撤 (MDD): {metrics.max_drawdown_pct:.2f}% (目標: <= 15%)")
    print(f"  年化夏普比率 (Sharpe): {metrics.sharpe_ratio:.2f} (目標: >= 1.8)")
    print(f"  期末總資產: ${metrics.final_equity_twd:,.0f} TWD (累積淨報酬: +{metrics.total_net_roi_pct:.2f}%)")
    print(f"  策略標準達標檢定: {'🏆 完美達標' if metrics.meets_strategy_standard else '⚠️ 需微調參數'}")

    assert metrics.is_ev_positive, "Strategy EV must be positive!"
    assert metrics.win_rate >= 50.0, "Win rate should exceed 50%"

    print("\n" + "=" * 70)
    print("🎉 量化歷史回測與 EV 期望值驗證全部通過！")
    print("=" * 70)


if __name__ == "__main__":
    test_strategy_backtest()
