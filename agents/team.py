# File: agents/team.py

'''CrewAI entry-point for the Taiwan Day Trading stock analysis pipeline.'''
from __future__ import annotations
import os
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from agents import decision_maker, news_analyst_agent, price_analyst_agent, researcher_agent
from agents.models import TradeSignal, TradeSide
from agents.tools.decision_tools import generate_trade_report, FinalPortfolioCheck

try:
    from crewai import Agent, Crew, Process, Task
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    Agent = Crew = Process = Task = Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)
HERE = Path(__file__).resolve().parent
_DEFAULT_TICKER = os.getenv('DEFAULT_TICKER', '2330')


def _build_tasks(
    ticker: str,
    researcher: Any,
    news_analyst: Any,
    price_analyst: Any,
    decision_maker: Any
) -> list[Any]:
    if not HAS_CREWAI:
        return []
    research_task = Task(
        description=f'請搜集 **{ticker}** 的最新股價資料與新聞。',
        expected_output='摘要報告',
        agent=researcher
    )
    news_task = Task(
        description=f'對 **{ticker}** 進行新聞面深度分析。',
        expected_output='新聞分析',
        agent=news_analyst,
        context=[research_task]
    )
    price_task = Task(
        description=f'對 **{ticker}** 跑一次技術指標計算。',
        expected_output='技術面分析',
        agent=price_analyst,
        context=[research_task]
    )
    decision_task = Task(
        description=f'綜合三組分析，裁定 **{ticker}** 買賣建議。',
        expected_output='TradeSignal JSON',
        agent=decision_maker,
        context=[research_task, news_task, price_task]
    )
    return [research_task, news_task, price_task, decision_task]


def create_crew(ticker: str, process: Any = None) -> Any:
    if not HAS_CREWAI:
        return None
    researcher = researcher_agent.create_researcher_agent()
    news_analyst = news_analyst_agent.create_news_analyst_agent()
    price_analyst = price_analyst_agent.create_price_analyst_agent()
    decision_agent = decision_maker.create_decision_maker_agent(ticker=ticker)
    tasks = _build_tasks(
        ticker=ticker,
        researcher=researcher,
        news_analyst=news_analyst,
        price_analyst=price_analyst,
        decision_maker=decision_agent
    )
    return Crew(
        agents=[researcher, news_analyst, price_analyst, decision_agent],
        tasks=tasks,
        process=process or Process.sequential,
        verbose=True,
        memory=False
    )


@dataclass
class CrewOutput:
    ticker: str
    signal: dict[str, Any]
    report: str
    summary: str
    raw_raw_outputs: dict[str, str] | None = None


def run_crew(ticker: str) -> CrewOutput:
    if not HAS_CREWAI:
        signal = decision_maker.synthesize_decision(ticker=ticker)
        report = generate_trade_report(signal=signal, analysis='Fallback mode without crewai')
        return CrewOutput(ticker=ticker, signal=signal, report=report, summary=_make_summary(ticker, signal))

    crew = create_crew(ticker=ticker)
    result = crew.kickoff(inputs={'ticker': ticker}) if crew else None
    signal = _parse_raw_result(result)

    try:
        portf_tool = FinalPortfolioCheck()
        portfolio_output = portf_tool.execute(portfolio_id='default')
    except Exception:
        portfolio_output = '無持倉摘要可用。'

    report = generate_trade_report(signal=signal, analysis='', portfolio=portfolio_output)
    return CrewOutput(
        ticker=ticker,
        signal=signal,
        report=report,
        summary=_make_summary(ticker, signal)
    )


def _parse_raw_result(result: Any) -> dict[str, Any]:
    if not result:
        return {'ticker': '', 'side': 'HOLD', 'confidence': 0.0, 'reason': 'empty result', 'price_target': None}
    text = str(result).strip()
    try:
        import json
        if '{' in text:
            idx = text.find('{')
            idx_end = text.rfind('}')
            return json.loads(text[idx:idx_end+1])
    except Exception:
        pass
    return {'ticker': '', 'side': 'HOLD', 'confidence': 0.5, 'reason': text[:200], 'price_target': None}


def _make_summary(ticker: str, signal: dict[str, Any]) -> str:
    side = signal.get('side', 'HOLD')
    conf = signal.get('confidence', 0.0)
    reason = signal.get('reason', '')
    return f"## {ticker} 交易結論\n- **方向**: {side}\n- **信心度**: {conf:.1%}\n- **原因**: {reason}"
