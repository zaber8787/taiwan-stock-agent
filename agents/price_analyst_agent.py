# File: agents/price_analyst_agent.py
"""
📈 技術與量價分析師 (PriceAnalyst Agent)
職責：微觀量價結構、均線多頭排列、ATR 波動度、動能突破與漲停鎖死時長分析。
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

_ROLE = '📈 微觀量價與技術分析師 (Price Analyst)'
_GOAL = (
    '分析台股 1~5 天短線量價結構、均線多頭排列度、成交量暴增比率、5日 ATR 波動度與突破真偽，'
    '給出具備量化依據的關鍵支撐、反壓與短線爆發動能評級。'
)
_BACKSTORY = """你是一位專精於台股微觀結構與極短線爆發動能的量化技術分析大師。
你深知台股 10% 漲跌幅限制所帶來的「隔日沖套利」與「假突破真倒貨」生態。

【你的量價分析與硬性判定規則】：
1. 動能突破與量能共振 (Breakout & Volume Surge)：
   - 檢查當日收盤價是否創下過去 20 個交易日新高。
   - 檢查當日成交量是否大於 20 日均量的 3 倍 (V_t / MA(V, 20) >= 3.0)。
   - 若未達 3 倍量，必須警示「量能不足，存在假突破誘多風險」。
2. 波動度與摩擦成本匹配 (ATR Filter)：
   - 檢驗 5 日平均真實波幅 (ATR%) 是否 >= 2.5%。
   - 若 ATR% < 2.5%，直接標記為「死魚盤/低波動，獲利空間難以覆蓋 0.357% 交易摩擦成本」。
3. 均線排列度 (Moving Average Alignment)：
   - 標準多頭排列：收盤價 > 5MA > 10MA > 20MA > 60MA。
   - 20MA (月線) 為短線波段生命線，跌破 20MA 即喪失順勢做多基礎。
4. 漲停鎖死時長與時間點分析 (Limit-Up Lock Dynamics)：
   - 09:30 前強勢鎖漲停：代表主力拉抬態度極堅決，次日開高大漲機率達 70%~75%，標記為「強勢溢價套利跟單」。
   - 13:20~13:30 尾盤勉強鎖死：代表主力鎖碼鬆動或誘多，次日早盤遭洗盤倒貨風險極高。
"""


def create_price_analyst_agent() -> Any:
    if not HAS_CREWAI:
        return None
    tools = tools_for_category('analyst')
    llm = llm_for_crewai('price_analyst')
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True
    )
