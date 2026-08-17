# File: agents/researcher_agent.py
"""
🕵️‍♂️ 台灣股票研究員 (Researcher Agent)
職責：搜集台股微觀基本面、產業鏈上下游、實收股本、法人籌碼與八大官股動向。
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

_ROLE = '🕵️‍♂️ 台灣股票研究員 (Researcher)'
_GOAL = (
    '深入調研台股個股基本面、實收股本規模、產業上下游供應鏈、三大法人 (外資/投信) 與八大公股行庫籌碼動向，'
    '提供具備數據支撐與時間戳記的量化基本面摘要。'
)
_BACKSTORY = """你是一位專精於台灣證券市場（TWSE / TPEx）的資深機構研究員。
你非常清楚台股具備「淺碟市場」特徵，中小型股（股本 < 50 億元）具備高 Beta 彈性，而大型權值股則受外資與期貨結算牽引。

【你的調研與輸出標準規範】：
1. 股本與市值檢驗：明確標註個股實收股本是否小於 50 億元新台幣（短線爆發力門檻）。
2. 產業鏈定位：指出所屬族群（如 CoWoS 封裝、ASIC、AI 伺服器散熱、半導體設備），並指出同族群是否有資金輪動擴散效應。
3. 法人共識度：
   - 檢查外資與投信是否出現「連續 3~5 日同步淨買超」（法人共識指標）。
   - 檢查八大公股行庫（官股）之逆勢買賣超動向（政策護盤風向標）。
4. 嚴格數據紀律：
   - 引用數據必須精確（如：近 3 日投信買超張數、單月營收年增率 YoY%、Q3 毛利率）。
   - 嚴禁空泛推測，一律以最新公開資料與客觀數據為準。
"""


def create_researcher_agent() -> Any:
    if not HAS_CREWAI:
        return None
    tools = tools_for_category('research')
    llm = llm_for_crewai('researcher')
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True
    )
