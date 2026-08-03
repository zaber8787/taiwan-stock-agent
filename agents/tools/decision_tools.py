# File: agents/tools/decision_tools.py

'''Decision-layer tools used by DecisionMaker agent (integrated with PaperTrader).'''
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
        from db.paper_trader import get_paper_trader
        pt = get_paper_trader()
        summary = pt.get_account_summary()
        holdings_str = ", ".join([f"{h['ticker']}:{h['shares']}股" for h in summary['holdings']]) or "無持倉"
        return f"Portfolio: 可用現金=${summary['cash']:,.2f}, 股票市值=${summary['holdings_value']:,.2f}, 總權益=${summary['total_equity']:,.2f}, 累積總損益=${summary['total_pnl']:,.2f} ({summary['total_roi_pct']:+.2f}%), 當前持倉:[{holdings_str}]"

    def _run(self, portfolio_id: str = "default") -> str:
        return self.execute(portfolio_id=portfolio_id)


def calculate_position_size(
    capital: float = 1000000.0,
    ticker: str = "2330",
    confidence: float = 0.5,
    risk_pct: float = 0.20
) -> PositionRecommendation:
    '''Compute recommended share count + all costs for a trade using PaperTrader rules.'''
    from db.paper_trader import get_paper_trader
    pt = get_paper_trader()
    alloc = pt.calculate_allocation(ticker=ticker, current_price=1000.0, confidence=confidence)
    shares = alloc['suggested_shares']
    entry_price = alloc['current_price']
    total_cost = shares * entry_price
    commission = max(20.0, total_cost * 0.001425)
    stamp_tax = total_cost * 0.003
    effective_cost = total_cost + commission

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
            '### 帳戶與持倉狀態',
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
