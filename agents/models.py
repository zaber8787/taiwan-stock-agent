# File: agents/models.py

'''Data models for the stock analysis framework.'''
from __future__ import annotations
import json
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Optional, Any


class TradeSide(str, Enum):
    '''Symbolic trade direction.'''
    BUY = 'BUY'
    SELL = 'SELL'
    HOLD = 'HOLD'


@dataclass
class TradeSignal:
    '''Atomic trade recommendation produced by the Decision Making agent.

    Attributes:
        ticker: Stock ticker (e.g. "2330", "2474").
        side: BUY / SELL / HOLD.
        confidence: Number in [0, 1] expressing analyst certainty.
        reason: Short rationale summarising the decision logic.
        price_target: Target price in TWD (used only for non-HOLD signals).
    '''
    ticker: str = ""
    side: TradeSide = TradeSide.HOLD
    confidence: float = 0.0
    reason: str = ""
    price_target: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'ticker': self.ticker,
            'side': self.side.value if isinstance(self.side, TradeSide) else str(self.side),
            'confidence': self.confidence,
            'reason': self.reason,
            'price_target': self.price_target
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradeSignal:
        side_raw = data.get('side', 'HOLD')
        try:
            side = TradeSide(side_raw)
        except ValueError:
            side = TradeSide.HOLD
        return cls(
            ticker=data.get('ticker', ''),
            side=side,
            confidence=float(data.get('confidence', 0.0)),
            reason=data.get('reason', ''),
            price_target=data.get('price_target')
        )


@dataclass
class PortfolioSnapshot:
    '''Current portfolio state read from DB.'''
    portfolio_id: str = ""
    cash: float = 0.0
    total_value: float = 0.0
    holdings: list[dict] = dc_field(default_factory=list)

    @property
    def equity(self) -> float:
        return self.total_value - self.cash


@dataclass
class PositionRecommendation:
    '''Recommended share count and costs from CalculatePositionSize.'''
    ticker: str
    shares: int
    entry_price: float
    total_cost: float
    commission: float
    stamp_tax: float
    effective_cost: float
    confidence: float
