# Source Generated with Decompyle++
# File: news_analyst_agent.cpython-311.pyc (Python 3.11)

'''NewsAnalyst — interprets news signals from a market perspective.'''
from __future__ import annotations
import logging
from typing import Any
from crewai import Agent
from agents.config import tools_for_category
logger = logging.getLogger(__name__)
_ROLE = '新聞分析師'
_GOAL = '判斷即時新聞事件的市場影響力，將重要資訊轉換為可行動的要點。'
_BACKSTORY = '你是資深財經記者出身，擅長從海量新聞中篩選出對短線交易有意義的信號。\n你會用簡潔的邏輯列出利多利空因素。'

def create_news_analyst_agent():
    tools = tools_for_category('analyst')()
    return Agent(role = _ROLE, goal = _GOAL, backstory = _BACKSTORY, llm = 'qwen2.5:7b', tools = tools, allow_delegation = False, verbose = True)

