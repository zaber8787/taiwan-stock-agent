# File: agents/team.py

'''CrewAI entry-point for the Taiwan Day Trading stock analysis pipeline with multi-stock support and debate system.'''
from __future__ import annotations
import os
import logging
import sys
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from agents import decision_maker, news_analyst_agent, price_analyst_agent, researcher_agent, risk_manager
from agents.models import TradeSignal, TradeSide, RiskStatus, RiskAssessment
from agents.tools.decision_tools import generate_trade_report, FinalPortfolioCheck
from agents.risk_manager import evaluate_trade_risk

# 新增：導入辯論系統
try:
    from agents.debate_system import run_debate, DebateResult
    HAS_DEBATE = True
except ImportError:
    HAS_DEBATE = False
    DebateResult = Any

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
_MAX_PARALLEL = int(os.getenv('MAX_PARALLEL_ANALYSIS', '10'))

# 辯論系統配置
DEBATE_ENABLED = os.getenv('DEBATE_ENABLED', 'true').lower() == 'true'
DEBATE_MAX_ROUNDS = int(os.getenv('DEBATE_MAX_ROUNDS', '3'))


def _build_tasks(
    ticker: str,
    researcher: Any,
    news_analyst: Any,
    price_analyst: Any,
    decision_maker: Any,
    risk_manager_agent: Any = None
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
        description=f'綜合三組分析與市場籌碼，裁定 **{ticker}** 投資方向 (BUY/SELL/HOLD) 與目標價。',
        expected_output='TradeSignal JSON',
        agent=decision_maker,
        context=[research_task, news_task, price_task]
    )
    tasks = [research_task, news_task, price_task, decision_task]
    if risk_manager_agent:
        risk_task = Task(
            description=f'對 **{ticker}** 的投資決策進行獨立風控審查 (大盤20MA、資金與產業集中度上限、停損停利點位)。',
            expected_output='RiskAssessment 審查說明',
            agent=risk_manager_agent,
            context=[decision_task]
        )
        tasks.append(risk_task)
    return tasks


def create_crew(ticker: str, process: Any = None) -> Any:
    if not HAS_CREWAI:
        return None
    researcher = researcher_agent.create_researcher_agent()
    news_analyst = news_analyst_agent.create_news_analyst_agent()
    price_analyst = price_analyst_agent.create_price_analyst_agent()
    decision_agent = decision_maker.create_decision_maker_agent(ticker=ticker)
    risk_agent = risk_manager.create_risk_manager_agent(ticker=ticker)
    tasks = _build_tasks(
        ticker=ticker,
        researcher=researcher,
        news_analyst=news_analyst,
        price_analyst=price_analyst,
        decision_maker=decision_agent,
        risk_manager_agent=risk_agent
    )
    return Crew(
        agents=[researcher, news_analyst, price_analyst, decision_agent, risk_agent],
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
    """運行分析 Crew，整合多空辯論與獨立風控審查"""
    if not HAS_CREWAI:
        signal = decision_maker.synthesize_decision(ticker=ticker)
        risk_assessment = evaluate_trade_risk(ticker=ticker, signal=signal)
        signal['risk_assessment'] = risk_assessment.to_dict()
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

    # 如果啟用辯論系統，運行多空辯論
    debate_result = None
    if DEBATE_ENABLED and HAS_DEBATE:
        try:
            logger.info(f"🎭 [Team] 啟用多空辯論系統：{ticker}")
            
            # 準備辯論所需的資料
            research_output = ""
            news_output = ""
            price_output = ""
            
            if result and hasattr(result, 'raw_outputs'):
                research_output = result.raw_outputs.get('research_task', '')[:1000]
                news_output = result.raw_outputs.get('news_task', '')[:1000]
                price_output = result.raw_outputs.get('price_task', '')[:1000]
            
            # 獲取籌碼資料
            from crawlers.chip_analyzer import analyze_chip_microstructure
            chip_info = analyze_chip_microstructure(ticker.replace('.TW', ''))
            
            # 運行辯論
            from agents.debate_system import run_debate
            debate_result = run_debate(
                ticker=ticker,
                research_data={
                    'news': news_output,
                    'technical': price_output,
                    'chip': chip_info
                }
            )
            
            logger.info(f"✅ [Team] 辯論完成：{ticker} -> {debate_result.final_decision} (信心度 {debate_result.confidence:.1%})")
            
            # 使用辯論結果更新決策
            signal = {
                'ticker': ticker,
                'side': debate_result.final_decision,
                'confidence': debate_result.confidence,
                'reason': debate_result.reasoning[:500],
                'debate_summary': {
                    'rounds': debate_result.total_rounds,
                    'quality': debate_result.debate_quality,
                    'bull_points': debate_result.bull_key_points,
                    'bear_points': debate_result.bear_key_points
                }
            }
            
        except Exception as e:
            logger.warning(f"⚠️ [Team] 辯論系統失敗，使用原決策：{e}")
            debate_result = None

    # 🛡️ 獨立風控審查 (Independent Risk Management Check)
    risk_assessment = evaluate_trade_risk(ticker=ticker, signal=signal)
    signal['risk_assessment'] = risk_assessment.to_dict()
    logger.info(f"🛡️ [Team] 風控審查完成：{ticker} -> {risk_assessment.status} ({risk_assessment.adjusted_shares // 1000} 張)")

    report = generate_trade_report(signal=signal, analysis='', portfolio=portfolio_output)
    
    # 如果有辯論結果，加入辯論摘要到報告
    if debate_result:
        report += f"\n\n## 🎭 多空辯論摘要\n- **辯論輪數**: {debate_result.total_rounds} 輪\n- **辯論質量**: {debate_result.debate_quality}\n- **看方要點**: {', '.join(debate_result.bull_key_points[:3])}\n- **空方要點**: {', '.join(debate_result.bear_key_points[:3])}"

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


async def run_crew_async(ticker: str, news_context: str | None = None) -> dict[str, Any]:
    '''Run crew analysis asynchronously for a single ticker.'''
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_crew, ticker)


async def analyze_multiple_stocks(tickers: list[str], news_context: str | None = None) -> list[dict[str, Any]]:
    '''Analyze multiple stocks in parallel with limited concurrency.
    
    Args:
        tickers: List of ticker codes to analyze
        news_context: Optional news context to include in analysis
        
    Returns:
        List of analysis results with signals for each ticker
    '''
    semaphore = asyncio.Semaphore(_MAX_PARALLEL)
    
    async def analyze_with_semaphore(ticker: str) -> dict[str, Any]:
        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    run_crew_async(ticker),
                    timeout=int(os.getenv('ANALYSIS_QUEUE_TIMEOUT', '300'))
                )
                return {
                    'ticker': ticker,
                    'signal': result.signal,
                    'report': result.report,
                    'summary': result.summary
                }
            except asyncio.TimeoutError:
                logger.warning(f"⏰ [Team] 分析超時：{ticker}")
                return {
                    'ticker': ticker,
                    'signal': {'side': 'HOLD', 'confidence': 0.0, 'reason': 'Analysis timeout'},
                    'report': 'Timeout',
                    'summary': f'{ticker} 分析超時'
                }
            except Exception as e:
                logger.error(f"❌ [Team] 分析失敗 {ticker}: {e}")
                return {
                    'ticker': ticker,
                    'signal': {'side': 'HOLD', 'confidence': 0.0, 'reason': f'Error: {e}'},
                    'report': f'Analysis error: {e}',
                    'summary': f'{ticker} 分析失敗'
                }
    
    tasks = [analyze_with_semaphore(ticker) for ticker in tickers]
    return await asyncio.gather(*tasks)
