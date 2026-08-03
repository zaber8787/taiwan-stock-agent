# Source Generated with Decompyle++
# File: price_analyst_agent.cpython-311.pyc (Python 3.11)

'''PriceAnalyst — technical analysis, chart reading patterns, momentum / trend signals.'''
from __future__ import annotations
import logging
from typing import Any
from crewai import Agent
from agents.config import tools_for_category
logger = logging.getLogger(__name__)
_ROLE = '技術分析師'
_GOAL = '透過成交量、均線、支撐/反壓等指標，判斷短期進出場時機。'
_BACKSTORY = '你是技術分析專家，擅長利用量價關係和常見指標為短線交易提供建議。'

def create_price_analyst_agent():
    tools = tools_for_category('analyst')()
    return Agent(role = _ROLE, goal = _GOAL, backstory = _BACKSTORY, llm = 'qwen2.5:7b', tools = tools, allow_delegation = False, verbose = True)

