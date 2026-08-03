# File: agents/price_analyst_agent.py

'''PriceAnalyst — technical analysis, chart reading patterns, momentum / trend signals.'''
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

_ROLE = '技術分析師'
_GOAL = '透過成交量、均線、支撐/反壓等指標，判斷短期進出場時機。'
_BACKSTORY = '你是技術分析專家，擅長利用量價關係和常見指標為短線交易提供建議。'


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
