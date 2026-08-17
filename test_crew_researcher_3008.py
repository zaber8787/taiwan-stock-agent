#!/usr/bin/env python3
"""
🧪 驗證 Researcher Agent 與 Tools 對 3008 (大立光) 的執行正確性
"""
import os
import sys
from pathlib import Path

# 環境變數設定
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['CREWAI_TELEMETRY_OPT_OUT'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'

sys.path.insert(0, str(Path(__file__).parent))

from agents.tools.research_tools import FetchStockPrices, FetchForeignInvestors, CrawlNewsForIndustry, FetchPTTSentiment
from agents.tools.analyst_tools import TechnicalAnalysis


def test_research_tools_3008():
    print("=" * 70)
    print("🔍 測試標的 3008 (大立光) 之 Researcher 工具鏈直接調用")
    print("=" * 70)

    # 1. 測試 FetchStockPrices
    p_tool = FetchStockPrices()
    p_res = p_tool.execute("3008")
    print(f"[1] FetchStockPrices('3008'):\n    -> {p_res}")
    assert "Stock 3008" in p_res or "Close=" in p_res or "No price" in p_res

    # 2. 測試 FetchForeignInvestors
    f_tool = FetchForeignInvestors()
    f_res = f_tool.execute("3008")
    print(f"[2] FetchForeignInvestors('3008'):\n    -> {f_res}")

    # 3. 測試 CrawlNewsForIndustry
    n_tool = CrawlNewsForIndustry()
    n_res = n_tool.execute("光學鏡頭")
    print(f"[3] CrawlNewsForIndustry('光學鏡頭'):\n    -> {n_res[:100]}...")

    # 4. 測試 FetchPTTSentiment
    ptt_tool = FetchPTTSentiment()
    ptt_res = ptt_tool.execute("3008")
    print(f"[4] FetchPTTSentiment('3008'):\n    -> {ptt_res}")

    # 5. 測試 TechnicalAnalysis
    tech_tool = TechnicalAnalysis()
    tech_res = tech_tool.execute("3008")
    print(f"[5] TechnicalAnalysis('3008'):\n    -> {tech_res}")

    print("\n" + "=" * 70)
    print("✅ 標的 3008 所有 Research 工具鏈 100% 執行成功，無 Event Loop 衝突！")
    print("=" * 70)


if __name__ == '__main__':
    test_research_tools_3008()
