# File: agents/team.py

'''CrewAI entry-point for the Taiwan Day Trading stock analysis pipeline.

Creates a :class:`~crewai.Crew` with four tasks:

 * ResearchTask            — run by the Researcher agent
 * NewsAnalysisTask        — run by the NewsAnalyst agent, inherits research output
 * PriceAnalysisTask       — run by the PriceAnalyst agent, inherits research output
 * DecisionTask            — run by the DecisionMaker, synthesises everything
'''
from __future__ import annotations
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from crewai import Agent, Crew, Process, Task
from agents import decision_maker, news_analyst_agent, price_analyst_agent, researcher_agent
from agents.models import TradeSignal, TradeSide
from agents.tools.decision_tools import generate_trade_report, FinalPortfolioCheck

logger = logging.getLogger(__name__)
HERE = Path(__file__).resolve().parent
_DEFAULT_TICKER = '2330'


def _build_tasks(
    ticker: str,
    researcher: Agent,
    news_analyst: Agent,
    price_analyst: Agent,
    decision_maker: Agent
) -> list[Task]:
    '''Construct the four chained crewai tasks and wire their results.'''
    research_task = Task(
        description=f'請搜集 **{ticker}** 的最新股價資料 (開盤/最高/最低/收盤/\n成交量)、外資買賣超紀錄、產業新聞摘要以及 PTT 社群情緒。\n回傳文字摘要，不要列出程式碼。保留完整的表格與標題。',
        expected_output='* 一份清晰的中文摘要，涵蓋:\n- 最近幾個交易日的 OHLCV 資料\n- 外資/陸資近數日動向\n- 主要產業相關新聞標題（限最近一周）\n- PTT 帖子中的情緒關鍵字（利多/利空）',
        agent=researcher
    )
    news_task = Task(
        description=f'根據資料研究員的摘要，對 **{ticker}** 進行新聞面深度分析:\n- 篩選出利多 / 利空因素；\n- 用 Qdrant 向量搜尋類似新聞 (top_k=5)；\n- 以企業檔 + 情緒分數輔助判斷;\n- 輸出利多/利空清單與信心分數。',
        expected_output='* 利多 / 利空因素清單（各 3-5 項），\n附簡要理由，若有相似文章附上標題與分數。',
        agent=news_analyst,
        context=[research_task]
    )
    price_task = Task(
        description=f'對 **{ticker}** 跑一次技術指標計算:\n- RSI (14)、EMA-20/60、Bollinger Bands(20, 2σ)\n- MACD 線 / 信號線 / 圖示量柱\n- 根據量價關係給出多/空/中性結論。',
        expected_output="* 一個短摘要: RSI 數值 + MACD 走向 + Bollinger 區間位置，\n最後一句話判斷為 '偏多' / '偏空' / '中性'。",
        agent=price_analyst,
        context=[research_task]
    )
    decision_task = Task(
        description=f'綜合三組分析，最終裁定對 **{ticker}** 的買賣建議。\n* TradeSignal: side ∈ BUY|SELL|HOLD;\n* confidence (0-1); reason — 一句話; price_target.',
        expected_output='以 `TradeSignal.to_dict()` JSON 格式輸出，\n含 ticker/side/confidence/reason/price_target。',
        agent=decision_maker,
        context=[research_task, news_task, price_task]
    )
    return [research_task, news_task, price_task, decision_task]


def create_crew(ticker: str, process: Process = Process.sequential) -> Crew:
    '''Build and return the :class:`~crewai.Crew` for *ticker*.'''
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
        process=process,
        verbose=True,
        memory=False
    )


@dataclass
class CrewOutput:
    '''Wrap the final crew result for callers.'''
    ticker: str
    signal: dict[str, Any]
    report: str
    summary: str
    raw_raw_outputs: dict[str, str] | None = None


def run_crew(ticker: str) -> CrewOutput:
    '''Build the crew, execute it, format outputs into a summary.'''
    crew = create_crew(ticker=ticker)
    result = crew.kickoff(inputs={'ticker': ticker})
    signal = _parse_raw_result(result)

    try:
        portf_tool = FinalPortfolioCheck()
        portfolio_output = portf_tool.execute(portfolio_id='default')
    except Exception:
        portfolio_output = '無持倉摘要可用。'

    report = generate_trade_report(signal=signal, analysis='', portfolio=portfolio_output)
    logger.info('team.run_crew completed for %s', ticker)
    return CrewOutput(
        ticker=ticker,
        signal=signal,
        report=report,
        summary=_make_summary(ticker, signal)
    )


def _parse_raw_result(result: Any) -> dict[str, Any]:
    '''Extract a TradeSignal-shaped dict from whatever crew returns.'''
    if not result:
        return {'ticker': '', 'side': 'HOLD', 'confidence': 0.0, 'reason': 'empty result', 'price_target': None}

    text = str(result).strip()
    if '```json' in text:
        idx_start = text.find('```json') + 7
        end_idx = text.find('```', idx_start)
        candidate = text[idx_start:end_idx].strip() if end_idx != -1 else text[idx_start:].strip()
    elif '{' in text:
        idx_start = text.find('{')
        end_idx = text.rfind('}')
        candidate = text[idx_start:end_idx + 1].strip() if end_idx != -1 else text[idx_start:].strip()
    else:
        candidate = text

    try:
        import json
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    import re
    pattern = r'(?:ticker|代碼)\s*[:=]\s*[\'\"]?(\w+)[\'\"]?\s*.*?(?:side|方向)\s*[:=]\s*[\'\"]?(BUY|SELL|HOLD)[\'\"]?\s*.*?(?:confidence|信心度)\s*[:=]\s*(\d[\d.\+]*)\s*'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return {
            'ticker': match.group(1).upper(),
            'side': match.group(2).upper(),
            'confidence': float(match.group(3)),
            'reason': text[:200],
            'price_target': None
        }

    return {
        'ticker': '',
        'side': 'HOLD',
        'confidence': 0.0,
        'reason': f'could not parse: {text[:200]}',
        'price_target': None
    }


def _make_summary(ticker: str, signal: dict[str, Any]) -> str:
    side = signal.get('side', 'HOLD')
    conf = signal.get('confidence', 0.0)
    reason = signal.get('reason', '')
    target = signal.get('price_target')

    target_str = f'${target:,.2f}' if target else '—'
    return f'## {ticker} 交易結論\n- **方向**: {side}\n- **信心度**: {conf:.1%}\n- **原因**: {reason}\n- **目標價**: {target_str}'


def main(ticker: str = _DEFAULT_TICKER, verbose: bool = True) -> None:
    '''Entry point. Runs the crew and prints the summary.'''
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s [%(name)s] %(message)s')
    crew_output = run_crew(ticker=ticker)
    print(f'\n=== 交易結論 ===\n{crew_output.summary}\n')
    print('=== 報告 ===\n', crew_output.report)
    logging.info('Done.')


if __name__ == '__main__':
    _ticker = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_TICKER
    main(ticker=_ticker)
