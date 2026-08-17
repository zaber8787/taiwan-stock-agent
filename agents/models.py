# File: agents/models.py

'''Data models for the stock analysis framework.'''
from __future__ import annotations
import json
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Optional, Any


from crawlers.event_classifier import EventCategory, EventUrgency, ImpactHorizon, ClassifiedEvent
from crawlers.market_regime import MarketRegime, StrategyMode, MarketState

class TradeSide(str, Enum):
    '''Symbolic trade direction.'''
    BUY = 'BUY'
    SELL = 'SELL'
    HOLD = 'HOLD'


class RiskStatus(str, Enum):
    '''Risk management evaluation status.'''
    APPROVED = 'APPROVED'   # 風控批准執行
    ADJUSTED = 'ADJUSTED'   # 風控調整部位或條件後批准
    REJECTED = 'REJECTED'   # 風控攔截否決


@dataclass
class RiskAssessment:
    '''Independent Risk Manager assessment output.

    Attributes:
        status: APPROVED / ADJUSTED / REJECTED.
        adjusted_shares: Recommended position shares after risk constraints.
        stop_loss_price: Hard stop-loss threshold price (e.g. -6%).
        take_profit_price: Trailing stop-profit activation threshold (e.g. +10%).
        max_holding_days: Maximum holding period in days (e.g. 4 for T+4).
        risk_factors: Identified risk triggers (e.g. market trend, concentration).
        risk_rationale: Explanation from the Risk Manager.
    '''
    status: RiskStatus = RiskStatus.APPROVED
    adjusted_shares: int = 0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    max_holding_days: int = 4
    risk_factors: list[str] = dc_field(default_factory=list)
    risk_rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status.value if isinstance(self.status, RiskStatus) else str(self.status),
            'adjusted_shares': self.adjusted_shares,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'max_holding_days': self.max_holding_days,
            'risk_factors': self.risk_factors,
            'risk_rationale': self.risk_rationale
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskAssessment:
        status_raw = data.get('status', 'APPROVED')
        try:
            status = RiskStatus(status_raw)
        except ValueError:
            status = RiskStatus.APPROVED
        return cls(
            status=status,
            adjusted_shares=int(data.get('adjusted_shares', 0)),
            stop_loss_price=data.get('stop_loss_price'),
            take_profit_price=data.get('take_profit_price'),
            max_holding_days=int(data.get('max_holding_days', 4)),
            risk_factors=list(data.get('risk_factors', [])),
            risk_rationale=str(data.get('risk_rationale', ''))
        )


@dataclass
class TradeSignal:
    '''Atomic trade recommendation produced by the Decision Making agent.

    Attributes:
        ticker: Stock ticker (e.g. "2330", "2474").
        side: BUY / SELL / HOLD.
        confidence: Number in [0, 1] expressing analyst certainty.
        reason: Short rationale summarising the decision logic.
        price_target: Target price in TWD (used only for non-HOLD signals).
        risk_assessment: Optional audit and constraints from RiskManager.
    '''
    ticker: str = ""
    side: TradeSide = TradeSide.HOLD
    confidence: float = 0.0
    reason: str = ""
    price_target: Optional[float] = None
    risk_assessment: Optional[RiskAssessment] = None

    def to_dict(self) -> dict[str, Any]:
        res = {
            'ticker': self.ticker,
            'side': self.side.value if isinstance(self.side, TradeSide) else str(self.side),
            'confidence': self.confidence,
            'reason': self.reason,
            'price_target': self.price_target
        }
        if self.risk_assessment:
            res['risk_assessment'] = self.risk_assessment.to_dict()
        return res

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradeSignal:
        side_raw = data.get('side', 'HOLD')
        try:
            side = TradeSide(side_raw)
        except ValueError:
            side = TradeSide.HOLD
        
        risk_data = data.get('risk_assessment')
        risk_obj = RiskAssessment.from_dict(risk_data) if isinstance(risk_data, dict) else None

        return cls(
            ticker=data.get('ticker', ''),
            side=side,
            confidence=float(data.get('confidence', 0.0)),
            reason=data.get('reason', ''),
            price_target=data.get('price_target'),
            risk_assessment=risk_obj
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
