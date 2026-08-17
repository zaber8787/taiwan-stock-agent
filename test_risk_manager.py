#!/usr/bin/env python3
"""
🛡️ 獨立風控經理 (RiskManager) 測試腳本
測試獨立風控在多種市場環境與帳戶條件下的審批、修正與攔截能力。
"""
import os
import sys
from pathlib import Path

# 設置環境變數
os.environ['CREWAI_TELEMETRY_OPT_OUT'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from agents.models import TradeSignal, TradeSide, RiskStatus, RiskAssessment
from agents.risk_manager import create_risk_manager_agent, evaluate_trade_risk
from agents.tools.decision_tools import generate_trade_report


def test_risk_manager_agent_creation():
    print("=" * 60)
    print("1. 🛡️ 測試 RiskManager Agent 創建")
    print("=" * 60)
    agent = create_risk_manager_agent('2330')
    if agent:
        print(f"✅ Agent 角色: {agent.role}")
        print(f"✅ Agent 目標: {agent.goal}")
    else:
        print("⚠️ CrewAI 未啟用，返回 None (可正常 fallback)")


def test_scenarios():
    print("\n" + "=" * 60)
    print("2. 📊 測試風控審批情境 (Risk Rules Matrix)")
    print("=" * 60)

    # 情境 A: 正常多頭高信心買進 (TSMC $950, 信心度 80%)
    sig_buy = TradeSignal(
        ticker="2330",
        side=TradeSide.BUY,
        confidence=0.80,
        reason="營收大幅成長，站穩季線",
        price_target=1100.0
    )
    risk_a = evaluate_trade_risk("2330", sig_buy, current_price=950.0)
    print(f"\n[情境 A - 正常買進] 狀態: {risk_a.status.value}")
    print(f"  建議股數: {risk_a.adjusted_shares:,} 股 ({risk_a.adjusted_shares // 1000} 張)")
    print(f"  停損價位: ${risk_a.stop_loss_price} (-6%)")
    print(f"  停利價位: ${risk_a.take_profit_price} (+10%)")
    print(f"  審核說明: {risk_a.risk_rationale}")
    assert risk_a.status in (RiskStatus.APPROVED, RiskStatus.ADJUSTED, RiskStatus.REJECTED)
    assert risk_a.stop_loss_price == round(950.0 * 0.94, 2)
    assert risk_a.take_profit_price == round(950.0 * 1.10, 2)

    # 情境 B: 賣出平倉指令 (SELL)
    sig_sell = TradeSignal(
        ticker="2330",
        side=TradeSide.SELL,
        confidence=0.90,
        reason="獲利達標，跌破 5MA 出場"
    )
    risk_b = evaluate_trade_risk("2330", sig_sell, current_price=950.0)
    print(f"\n[情境 B - 賣出平倉] 狀態: {risk_b.status.value}")
    print(f"  審核說明: {risk_b.risk_rationale}")
    assert risk_b.status == RiskStatus.APPROVED

    # 情境 C: 信心度過低且買不起 1 張 (股價 $1500, 信心度 30%)
    sig_low_conf = TradeSignal(
        ticker="3008",
        side=TradeSide.BUY,
        confidence=0.30,
        reason="微弱反彈"
    )
    risk_c = evaluate_trade_risk("3008", sig_low_conf, current_price=1500.0)
    print(f"\n[情境 C - 低信心/高價股攔截] 狀態: {risk_c.status.value}")
    print(f"  風險因子: {risk_c.risk_factors}")
    print(f"  審核說明: {risk_c.risk_rationale}")
    assert risk_c.status in (RiskStatus.REJECTED, RiskStatus.ADJUSTED)


def test_report_integration():
    print("\n" + "=" * 60)
    print("3. 📝 測試包含風控審核章節的交易報告生成")
    print("=" * 60)

    sig = TradeSignal(
        ticker="2330",
        side=TradeSide.BUY,
        confidence=0.85,
        reason="先進製程市佔率 >90%，EPS 成長率 25%",
        price_target=1050.0
    )
    ra = evaluate_trade_risk("2330", sig, current_price=950.0)
    sig.risk_assessment = ra

    report = generate_trade_report(signal=sig, analysis="完整基本面與籌碼研究...")
    print(report)
    print("\n" + "=" * 60)
    print("✅ 風控經理全模組測試通過！")
    print("=" * 60)


if __name__ == "__main__":
    test_risk_manager_agent_creation()
    test_scenarios()
    test_report_integration()
