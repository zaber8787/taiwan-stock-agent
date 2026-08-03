# File: agents/tools/decision_tools.py

'''Decision-layer tools used by DecisionMaker agent.'''
from __future__ import annotations
import textwrap
from typing import Any
from agents.tools.base import BaseTool
from agents.models import TradeSignal, PositionRecommendation


class FinalPortfolioCheck(BaseTool):
    """Read the current portfolio holdings, cash, and equity."""
    name: str = "FinalPortfolioCheck"
    description: str = "Read the current portfolio holdings, cash, and equity."

    def execute(self, portfolio_id: str = "default") -> str:
        from db.mongo_client import get_mongo_client
        mc = get_mongo_client()
        doc = mc.find_one("portfolio", {"portfolio_id": portfolio_id})
        if doc:
            return f"Portfolio {portfolio_id}: cash=${doc.get('cash', 0):,.2f}, total_value=${doc.get('total_value', 0):,.2f}"
        return f"Portfolio {portfolio_id}: cash=$1,000,000.00, total_value=$1,000,000.00 (default)"

    def _run(self, portfolio_id: str = "default") -> str:
        return self.execute(portfolio_id=portfolio_id)


def calculate_position_size(
    capital: float = 1000000.0,
    ticker: str = "2330",
    confidence: float = 0.5,
    risk_pct: float = 0.1
) -> PositionRecommendation:
    '''Compute recommended share count + all costs for a trade.'''
    budget = capital * min(max(confidence * risk_pct, 0.01), 0.2)
    entry_price = 100.0
    shares = max(int(budget / (entry_price * 1000)) * 1000, 1000)
    total_cost = shares * entry_price
    commission = total_cost * 0.001425
    stamp_tax = total_cost * 0.003
    effective_cost = total_cost + commission + stamp_tax

    return PositionRecommendation(
        ticker=ticker,
        shares=shares,
        entry_price=entry_price,
        total_cost=total_cost,
        commission=commission,
        stamp_tax=stamp_tax,
        effective_cost=effective_cost,
        confidence=confidence
    )


def generate_trade_report(
    signal: Any,
    analysis: str = "",
    portfolio: Any = None
) -> str:
    '''Assemble a concise markdown trade report for the operator.'''
    if not isinstance(signal, TradeSignal):
        if isinstance(signal, dict):
            signal = TradeSignal.from_dict(signal)
        else:
            signal = TradeSignal()

    side_val = signal.side.value if hasattr(signal.side, 'value') else signal.side
    lines = [
        '# 📊 交易報告',
        '',
        '| 項目 | 內容 |',
        '| --- | --- |',
        f'| 代碼 | {signal.ticker} |',
        f'| 方向 | **{side_val}** |',
        f'| 信心度 | {signal.confidence:.0%} |'
    ]
    if signal.price_target:
        lines.append(f'| 目標價 | ${signal.price_target:+,.2f} |')
    else:
        lines.append('| 目標價 | — |')

    lines.extend(['', '### 理由', f'> {signal.reason}', ''])

    if portfolio:
        lines.extend([
            '### 持倉摘要',
            f'- {portfolio}',
            ''
        ])

    if analysis:
        lines.extend([
            '### 原始分析摘要',
            textwrap.shorten(analysis, width=1500, placeholder='…'),
            ''
        ])

    return '\n'.join(lines).strip()
