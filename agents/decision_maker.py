# File: agents/decision_maker.py

'''DecisionMaker — synthesizes outputs from the research/news/price branches 
into a single TradeSignal.'''
from __future__ import annotations
import logging
from typing import Any
from agents.config import tools_for_category, llm_for_crewai
from agents.models import TradeSignal, TradeSide, PortfolioSnapshot

try:
    from crewai import Agent
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    Agent = Any

logger = logging.getLogger(__name__)

_ROLE = '決策主管'
_GOAL = '綜合研究員、新聞分析師和技術分析師的報告，給出清晰的多空方向與理由。\n只依賴有說服力的數據，輸出格式為 JSON-like TradeSignal。'
_BACKSTORY = '你是一位紀律嚴謹的交易主管，擅長在紛雜資訊中保持客觀與冷靜，\n只採用有說服力的證據來下單。決策需有明確的理由支撐。'


def create_decision_maker_agent(ticker: str | None = None) -> Any:
    '''Return the DecisionMaker agent configured with all required tools.'''
    if not HAS_CREWAI:
        return None
    tools = tools_for_category('decision')
    llm = llm_for_crewai('decision_maker')
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True
    )


def synthesize_decision(
    ticker: str,
    research_output: str = "",
    news_output: str = "",
    price_output: str = "",
    portfolio_output: str = ""
) -> dict[str, Any]:
    '''Synthesize the four inputs and return a simple text decision.'''
    try:
        sentiment = _quick_heuristic(
            research=research_output,
            news=news_output,
            price=price_output,
            portfolio=portfolio_output
        )
        return {
            'ticker': ticker,
            'side': sentiment['side'],
            'confidence': sentiment['confidence'],
            'reason': sentiment['rreason'],
            'raw_decision': f"Synthesized decision for {ticker}"
        }
    except Exception as exc:
        logger.exception('decision synthesis failed')
        return {
            'ticker': ticker,
            'side': 'HOLD',
            'confidence': 0.0,
            'reason': f'Error during synthesis: {exc}',
            'raw_decision': ''
        }


def _quick_heuristic(
    research: str = "",
    news: str = "",
    price: str = "",
    portfolio: str = ""
) -> dict[str, Any]:
    '''A deterministic heuristic that combines the three signals.'''
    counts = [0, 0, 0]

    def _classify(text: str, bucket_index: int) -> None:
        if not text:
            return
        lower = text.lower()
        buy_words = {'買進', '看多', '站穩', '上攻', '翻紅', '利好', '營收', '熱絡', '出貨', '強勁'}
        sell_words = {'賣出', '看空', '跌破', '反壓', '翻黑', '利空', '衰退'}
        if any(w in lower for w in buy_words):
            counts[0] += 1
        elif any(w in lower for w in sell_words):
            counts[1] += 1
        else:
            counts[2] += 1

    _classify(research, 0)
    _classify(news, 1)
    _classify(price, 2)

    max_count = max(counts)
    if counts[0] == max_count and counts[0] > 0:
        side = 'BUY'
    elif counts[1] == max_count and counts[1] > 0:
        side = 'SELL'
    else:
        side = 'HOLD'

    confidence = round(max(0.70, max_count / 3.0), 2) if side != 'HOLD' else 0.5
    return {
        'side': side,
        'confidence': confidence,
        'rreason': f'majority vote among 3 branches: signal={side}'
    }
