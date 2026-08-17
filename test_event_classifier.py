#!/usr/bin/env python3
"""
🏷️ 金融事件分類系統測試腳本 (Event Classifier Test)
測試 7 大核心事件類型識別、緊急度評級、影響時間維度與情緒判斷。
"""
import os
import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from crawlers.event_classifier import classify_news_event, EventCategory, EventUrgency, ImpactHorizon


def test_event_classification():
    print("=" * 70)
    print("🏷️ 金融事件分類系統 (Event Classification Matrix) 測試")
    print("=" * 70)

    test_cases = [
        {
            "id": 1,
            "title": "台積電公布 Q3 財報 EPS 達 12.5 元創歷史新高，法說會上修全年毛利率展望",
            "summary": "晶圓代工龍頭台積電今日召開法說會，受惠 AI HPC 強勁需求，單季營收與每股盈餘同步寫下歷史新高。",
            "expected_cat": EventCategory.EARNINGS
        },
        {
            "id": 2,
            "title": "聯發科斥資 30 億元併購海外 ASIC 晶片設計廠，擴大資本支出布局 AI 伺服器",
            "summary": "IC 設計大廠聯發科宣布透過策略併購與合資方式取得海外先進封裝設計專利，加速切入雲端服務供應商。",
            "expected_cat": EventCategory.MA_EXPANSION
        },
        {
            "id": 3,
            "title": "美國商務部擴大 AI 晶片出口管制禁令，證交所將多檔概念股列入注意股票處置",
            "summary": "受地緣政治與反壟斷法規收緊影響，相關伺服器概念股面臨列入注意股與暫停當沖處置，金管會密切關注。",
            "expected_cat": EventCategory.REGULATORY_LEGAL
        },
        {
            "id": 4,
            "title": "輝達傳擴大追加 CoWoS 先進封裝訂單，台積電代工報價調漲 5%",
            "summary": "供應鏈消息指出，Nvidia 針對 Blackwell 架構新晶片向台系供應鏈緊急追單，帶動關鍵零組件交期延長。",
            "expected_cat": EventCategory.SUPPLY_CHAIN
        },
        {
            "id": 5,
            "title": "廣達董事會決議買回庫藏股 2 萬張，大股東與董監持股申報轉讓同步暫緩",
            "summary": "為維護公司信用與股東權益，廣達今日公告啟動庫藏股買回計畫，展現經營階層護盤決心。",
            "expected_cat": EventCategory.MANAGEMENT_INSIDER
        },
        {
            "id": 6,
            "title": "美國聯準會 Fed 宣布降息 2 碼，央行維持利率政策並密切觀察通膨 CPI",
            "summary": "全球主要央行政策轉向寬鬆，國安基金持續關注外資資金回流台股動向。",
            "expected_cat": EventCategory.MACRO_MARKET
        },
        {
            "id": 7,
            "title": "PTT 股票板熱議台積電千元保衛戰，網友盛傳主力大戶借券軋空消息",
            "summary": "社群平台針對科技權值股走勢爆料不斷，小道消息傳出投顧主力資金正積極進場炒作。",
            "expected_cat": EventCategory.SENTIMENT_RUMOR
        }
    ]

    all_passed = True
    for tc in test_cases:
        res = classify_news_event(tc['title'], tc['summary'])
        passed = (res.category == tc['expected_cat'])
        if not passed:
            all_passed = False
        
        status_mark = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n[{tc['id']}] {status_mark} | 標題: {tc['title'][:45]}...")
        print(f"    👉 分類結果: {res.category_name_zh} ({res.category.value})")
        print(f"    👉 緊急程度: {res.urgency.value} | 影響週期: {res.impact_horizon.value} | 多空傾向: {res.sentiment_hint}")
        print(f"    👉 命中特徵: {', '.join(res.keywords_matched)}")
        assert passed, f"Expected {tc['expected_cat']}, got {res.category}"

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 7 大核心事件分類測試全部 100% 通過！")
    else:
        print("⚠️ 部份測試案例未通過，請檢查關鍵詞權重庫。")
    print("=" * 70)


if __name__ == "__main__":
    test_event_classification()
