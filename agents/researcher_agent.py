# Source Generated with Decompyle++
# File: researcher_agent.cpython-311.pyc (Python 3.11)

'''Researcher — gathers raw data about a TWSE stock.'''
from __future__ import annotations
import logging
from typing import Any
from crewai import Agent
from agents.config import tools_for_category
logger = logging.getLogger(__name__)
_ROLE = '台灣股票研究員'
_GOAL = '搜集台股市況、個股資料、產業新聞，提供清晰的脈絡給決策者。'
_BACKSTORY = '你是一位經驗豐富的台股研究員，擅長從各類公開資訊中整理出有價值的\n投資線索。你需要用中文撰寫摘要，並標明資訊來源與時間。'

def create_researcher_agent():
    tools = tools_for_category('research')()
    return Agent(role = _ROLE, goal = _GOAL, backstory = _BACKSTORY, llm = 'qwen2.5:7b', tools = tools, allow_delegation = False, verbose = True)

