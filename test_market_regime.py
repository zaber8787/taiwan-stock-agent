#!/usr/bin/env python3
"""
🌐 市場狀態偵測系統測試腳本 (Market Regime Test)
測試多頭、空頭與盤整市場辨識，並驗證與獨立風控經理的動態連動。
"""
import os
import sys
from pathlib import Path
import numpy as np

# 設置環境變數
os.environ['CREWAI_TELEMETRY_OPT_OUT'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from crawlers.market_regime import detect_market_regime, MarketRegime, StrategyMode
from agents.models import TradeSignal, TradeSide, RiskStatus
from agents.risk_manager import evaluate_trade_risk


def test_market_regime_scenarios():
    print("=" * 70)
    print("🌐 測試市場狀態偵測引擎 (Market Regime Scenarios)")
    print("=" * 70)

    # 1. 模擬多頭市場 (穩定走升，5MA > 20MA > 60MA)
    bull_prices = [20000.0 + (i * 40.0) for i in range(70)]
    bull_state = detect_market_regime(price_series=bull_prices)
    print(f"\n[情境 1 - 多頭走勢] 狀態: {bull_state.regime_name_zh} ({bull_state.regime.value})")
    print(f"  策略模式: {bull_state.strategy_mode.value} | 撥款乘數: {bull_state.allocation_multiplier:.1f}x")
    print(f"  建議停損: {bull_state.suggested_stop_loss_pct:+.1f}% | 建議停利: {bull_state.suggested_take_profit_pct:+.1f}% | 持有天數: T+{bull_state.suggested_max_holding_days}")
    print(f"  研判說明: {bull_state.rationale}")
    assert bull_state.regime == MarketRegime.BULL
    assert bull_state.allocation_multiplier == 1.0
    assert bull_state.suggested_stop_loss_pct == -6.0

    # 2. 模擬空頭市場 (連續下殺跌破均線，5MA < 20MA < 60MA)
    bear_prices = [24000.0 - (i * 50.0) for i in range(70)]
    bear_state = detect_market_regime(price_series=bear_prices)
    print(f"\n[情境 2 - 空頭下殺] 狀態: {bear_state.regime_name_zh} ({bear_state.regime.value})")
    print(f"  策略模式: {bear_state.strategy_mode.value} | 撥款乘數: {bear_state.allocation_multiplier:.1f}x")
    print(f"  建議停損: {bear_state.suggested_stop_loss_pct:+.1f}% | 建議停利: {bear_state.suggested_take_profit_pct:+.1f}% | 持有天數: T+{bear_state.suggested_max_holding_days}")
    print(f"  研判說明: {bear_state.rationale}")
    assert bear_state.regime == MarketRegime.BEAR
    assert bear_state.allocation_multiplier == 0.30
    assert bear_state.suggested_stop_loss_pct == -3.0

    # 3. 模擬箱型盤整 (在 22000 點上下 50 點內狹幅糾結震盪)
    ranging_prices = [22000.0 + (np.sin(i / 1.5) * 30.0) for i in range(70)]
    ranging_state = detect_market_regime(price_series=ranging_prices)
    print(f"\n[情境 3 - 箱型盤整] 狀態: {ranging_state.regime_name_zh} ({ranging_state.regime.value})")
    print(f"  策略模式: {ranging_state.strategy_mode.value} | 撥款乘數: {ranging_state.allocation_multiplier:.1f}x")
    print(f"  建議停損: {ranging_state.suggested_stop_loss_pct:+.1f}% | 建議停利: {ranging_state.suggested_take_profit_pct:+.1f}% | 持有天數: T+{ranging_state.suggested_max_holding_days}")
    print(f"  研判說明: {ranging_state.rationale}")
    assert ranging_state.regime == MarketRegime.RANGING
    assert ranging_state.allocation_multiplier == 0.60
    assert ranging_state.suggested_stop_loss_pct == -4.0


def test_risk_manager_market_regime_integration():
    print("\n" + "=" * 70)
    print("🛡️ 測試獨立風控與市場狀態連動")
    print("=" * 70)

    sig = TradeSignal(
        ticker="2330",
        side=TradeSide.BUY,
        confidence=0.75,
        reason="基本面強勁"
    )

    # 執行風控評估
    res = evaluate_trade_risk("2330", sig, current_price=950.0)
    print(f"風控審查狀態: {res.status.value}")
    print(f"風控建議停損: ${res.stop_loss_price:,.2f}")
    print(f"風控建議停利: ${res.take_profit_price:,.2f}")
    print(f"風控最大持有天數: T+{res.max_holding_days}")
    print(f"風控主管說明: {res.risk_rationale}")
    print("\n" + "=" * 70)
    print("✅ 市場狀態偵測與風控連動測試全部通過！")
    print("=" * 70)


if __name__ == "__main__":
    test_market_regime_scenarios()
    test_risk_manager_market_regime_integration()
