# File: agents/news_analyst_agent.py

'''NewsAnalyst — interprets news signals from a market perspective.'''
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

_ROLE = '新聞分析師'
_GOAL = '判斷即時新聞事件的市場影響力，將重要資訊轉換為可行動的要點。'
_BACKSTORY = '你是資深財經記者出身，擅長從海量新聞中篩選出對短線交易有意義的信號。你會用簡潔的邏輯列出利多利空因素。'


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
