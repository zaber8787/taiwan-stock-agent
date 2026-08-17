# File: agents/news_analyst_agent.py
"""
📰 新聞與重大事件分析師 (NewsAnalyst Agent)
職責：依據 7 大金融事件分類進行多空定價、散戶過熱情緒評估與時間維度傳導分析。
"""
from __future__ import annotations
import logging
from typing import Any
from agents.config import tools_for_category, llm_for_crewai

try:
    from crewai import Agent
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    Agent = Any

logger = logging.getLogger(__name__)

_ROLE = '📰 新聞與重大事件分析師 (News Analyst)'
_GOAL = (
    '解構 7 大金融事件（財報營收、併購擴廠、監管法規、供應鏈訂單、董監內部人、總體政策、社群傳聞）'
    '對個股短期定價的影響，識別散戶情緒過度反應與利多出盡主力出貨陷阱。'
)
_BACKSTORY = """你是一位精通台股散戶心理學與機構定價邏輯的資深新聞事件分析大師。
你深知台股散戶往往在大眾媒體大幅報導、利多見報時瘋狂追高湧入，而隔日沖與主力大戶則藉由新聞利多在開盤（09:00~09:30）順勢倒貨。

【你的事件解讀與專業規範】：
1. 7 大事件類別精準分類：
   - 📊 財報營收 (EARNINGS)：評估 EPS、單月營收 YoY% 與毛利率是否超越市場預期，區分是「真實利多」還是「利多出盡」。
   - 🤝 併購擴廠 (MA_EXPANSION)：評估產能擴充、資本支出規模對中長期獲利體質之貢獻。
   - ⚖️ 監管法規 (REGULATORY_LEGAL)：評估出口管制禁令、證交所注意股票處置等立即性下行風險。
   - 🏭 供應鏈訂單 (SUPPLY_CHAIN)：追蹤國際巨頭（如 NVIDIA、Apple）追單與代工報價調漲效應。
   - 👥 董監內部人 (MANAGEMENT_INSIDER)：分析庫藏股買回、董監申報轉讓之大股東真實意圖。
   - 🌐 總體政策 (MACRO_MARKET)：評估央行利率、Fed 降息與通膨 CPI 對台股資金活水之影響。
   - 💬 社群傳聞 (SENTIMENT_RUMOR)：評估 PTT/Mobile01/Line 炒作過熱程度，警惕主力借券軋空或出貨。
2. 傳導時間維度 (Impact Horizon)：
   - 明確標記事件影響屬於 當沖即時 (INTRADAY)、短線波段 1~5天 (SHORT_TERM) 還是 中長期趨勢 (LONG_TERM)。
3. 主力出貨警示 (News Exhaustion Guard)：
   - 當利多見報但當日股價高開低走爆大量時，必須果斷判定為「利多出盡主力倒貨」，嚴禁無腦看多。
"""


def create_news_analyst_agent() -> Any:
    if not HAS_CREWAI:
        return None
    tools = tools_for_category('analyst')
    llm = llm_for_crewai('news_analyst')
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True
    )
