#!/usr/bin/env python3
"""
多空辯論系統測試腳本

測試流程：
1. 模擬一個股票分析情境
2. 運行多空辯論
3. 展示辯論結果
"""
import os
import sys
from pathlib import Path

# 設置環境變數
os.environ['DEBATE_ENABLED'] = 'true'
os.environ['DEBATE_MAX_ROUNDS'] = '2'

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from agents.debate_system import DebateSystem, DebateArgument, DebateResult


def test_basic_debate():
    """測試基本辯論功能"""
    print("=" * 60)
    print("🎭 多空辯論系統測試")
    print("=" * 60)
    
    system = DebateSystem()
    
    # 模擬研究資料
    research_data = {
        'price_data': '2330: Close=$950.00, +2.5%, Volume=50M',
        'news': '台積電宣布新製程突破，營收成長預期上調',
        'technical': 'RSI=65, 站穩 MA20, 突破整理型態',
        'chip': '家數減少，分點集中度提高'
    }
    
    print("\n📊 測試標的：2330 (台積電)")
    print(f"📝 新聞：{research_data['news']}")
    print(f"📈 技術：{research_data['technical']}")
    print(f"💰 籌碼：{research_data['chip']}")
    
    print("\n⏳ 開始運行多空辯論...")
    
    # 運行辯論
    result = system.run_debate('2330', research_data)
    
    # 顯示結果
    print("\n" + "=" * 60)
    print("📋 辯論結果")
    print("=" * 60)
    
    print(f"\n🎯 最終決策：{result.final_decision}")
    print(f"📊 信心度：{result.confidence:.1%}")
    print(f"📝 辯論質量：{result.debate_quality}")
    print(f"🔄 辯論輪數：{result.total_rounds}")
    
    print(f"\n🐂 看方要點:")
    for i, point in enumerate(result.bull_key_points[:3], 1):
        print(f"  {i}. {point}")
    
    print(f"\n🐻 看空要點:")
    for i, point in enumerate(result.bear_key_points[:3], 1):
        print(f"  {i}. {point}")
    
    print(f"\n💡 決策理由:")
    print(f"  {result.reasoning[:300]}...")
    
    print("\n" + "=" * 60)
    print("✅ 測試完成!")
    print("=" * 60)
    
    return result


def test_debate_arguments():
    """測試論點結構"""
    print("\n" + "=" * 60)
    print("📝 論點結構測試")
    print("=" * 60)
    
    bull = DebateArgument(
        side='bull',
        main_points=[
            '營收年增 25%，超預期',
            '新製程量產，毛利率提升',
            'AI 伺服器需求強勁'
        ],
        evidence=[
            'Q3 營收達 $50B，YoY +25%',
            '7nm 製程佔比提升至 45%',
            'AI 客戶訂單已排至明年 Q2'
        ],
        confidence=0.85,
        reasoning='基本面向上，技術面突破，籌碼集中'
    )
    
    bear = DebateArgument(
        side='bear',
        main_points=[
            '估值已偏高，PER 35 倍',
            '地緣政治風險升溫',
            '半導體週期可能見頂'
        ],
        evidence=[
            'PER 高於歷史平均 28 倍',
            '中美貿易摩擦加劇',
            '記憶體價格開始下跌'
        ],
        confidence=0.75,
        reasoning='估值過高，風險報酬比不佳'
    )
    
    print(f"\n🐂 Bull 論點:")
    for i, point in enumerate(bull.main_points, 1):
        print(f"  {i}. {point}")
    print(f"   證據：{', '.join(bull.evidence[:2])}")
    print(f"   信心度：{bull.confidence:.1%}")
    
    print(f"\n🐻 Bear 論點:")
    for i, point in enumerate(bear.main_points, 1):
        print(f"  {i}. {point}")
    print(f"   證據：{', '.join(bear.evidence[:2])}")
    print(f"   信心度：{bear.confidence:.1%}")
    
    print("\n✅ 論點結構測試完成!")


def test_debate_integration():
    """測試與 team.py 的整合"""
    print("\n" + "=" * 60)
    print("🔗 與 stock-agent 整合測試")
    print("=" * 60)
    
    try:
        from agents.team import run_crew, HAS_DEBATE, DEBATE_ENABLED
        
        print(f"✅ 辯論系統已導入：{HAS_DEBATE}")
        print(f"✅ 辯論功能已啟用：{DEBATE_ENABLED}")
        
        # 測試單一股票分析（如果啟用辯論，會自動運行辯論）
        print("\n⚠️  注意：完整運行需要 CrewAI 和相關依賴")
        print("   這裡只測試整合性，不實際運行完整分析")
        
        print("\n✅ 整合測試完成!")
        
    except Exception as e:
        print(f"❌ 整合測試失敗：{e}")


def main():
    """主測試流程"""
    print("\n" + "🎭" * 30)
    print("  多空辯論系統完整測試")
    print("🎭" * 30 + "\n")
    
    # 1. 測試論點結構
    test_debate_arguments()
    
    # 2. 測試基本辯論
    test_basic_debate()
    
    # 3. 測試整合
    test_debate_integration()
    
    print("\n" + "=" * 60)
    print("🎉 所有測試完成!")
    print("=" * 60)
    
    print("\n💡 使用建議:")
    print("  1. 設置 .env 中的 DEBATE_ENABLED=true 啟用辯論")
    print("  2. 調整 DEBATE_MAX_ROUNDS 控制辯論輪數")
    print("  3. 辯論結果會自動整合到交易決策中")
    print("  4. 辯論摘要會顯示在 Discord 通知中")
    
    print("\n📚 文件位置:")
    print("  - 辯論系統：agents/debate_system.py")
    print("  - 整合入口：agents/team.py")
    print("  - 環境配置：.env.example")


if __name__ == '__main__':
    main()
