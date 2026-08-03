# File: agents/decision_maker.py

'''DecisionMaker — synthesizes outputs from the research/news/price branches 
into a single TradeSignal.'''
from __future__ import annotations
import logging
from typing import Any
from crewai import Agent
from agents.config import tools_for_category
from agents.models import TradeSignal, TradeSide, PortfolioSnapshot

logger = logging.getLogger(__name__)

_ROLE = '決策主管'
_GOAL = '綜合研究員、新聞分析師和技術分析師的報告，給出清晰的多空方向與理由。\n只依賴有說服力的數據，輸出格式為 JSON-like TradeSignal。'
_BACKSTORY = '你是一位紀律嚴謹的交易主管，擅長在紛雜資訊中保持客觀與冷靜，\n只採用有說服力的證據來下單。決策需有明確的理由支撐。'
_PROMPT_TEMPLATE = '## 任務 — 決定對 {ticker} 的最終操作\n\n綜合以下三個來源：\n\n1. **Researcher** (資料研究員):\n{research_output}\n\n2. **NewsAnalyst** (新聞分析師):\n{news_output}\n\n3. **PriceAnalyst** (技術分析師):\n{price_output}\n\n4. **Portfolio Snapshot**:\n{portfolio_output}\n\n請用中文給出最終判斷，輸出格式為：\n<decision>\nticker: <代碼>\nside: <BUY|SELL|HOLD>\nconfidence: 0-1 數值\nreason: <原因簡述>\nprice_target: <目標價 或 N/A>\n</decision>\n'


def create_decision_maker_agent(ticker: str | None = None) -> Agent:
    '''Return the DecisionMaker agent configured with all required tools.'''
    tools = tools_for_category('decision')()
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm='qwen2.5:7b',
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
    '''Synthesize the four inputs and return a simple text decision.

    Falls back to a "default HOLD" when any part is empty or errors out.
    '''
    try:
        prompt = _build_prompt(
            ticker=ticker,
            research=research_output[:1600],
            news=news_output[:1600],
            price=price_output[:1600],
            portfolio=portfolio_output[:500]
        )
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
            'raw_decision': prompt
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
        buy_words = {'買進', '看多', '站穩', '上攻', '翻紅', '利好'}
        sell_words = {'賣出', '看空', '跌破', '反壓', '翻黑', '利空'}
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
    if counts[0] == max_count:
        side = 'BUY'
    elif counts[1] == max_count:
        side = 'SELL'
    else:
        side = 'HOLD'

    confidence = round(max_count / 3.0, 2)
    return {
        'side': side,
        'confidence': confidence,
        'rreason': f'majority vote among 3 branches: counts={counts}, signal={side}'
    }


def _build_prompt(
    ticker: str,
    research: str = "",
    news: str = "",
    price: str = "",
    portfolio: str = ""
) -> str:
    out = []
    out.append(f'## Ticker: {ticker}')
    out.append('### 資料研究')
    out.append(research)
    out.append('### 新聞分析')
    out.append(news)
    out.append('### 技術分析')
    out.append(price)
    out.append('### 持倉摘要')
    out.append(portfolio)
    return '\n---\n'.join(out).strip()
