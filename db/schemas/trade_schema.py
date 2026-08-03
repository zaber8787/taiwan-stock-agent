# File: db/schemas/trade_schema.py

'''Pydantic models for trade records.'''
from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Side(str, Enum):
    '''Order direction.'''
    BUY = 'BUY'
    SELL = 'SELL'


COMMISSION_RATE = 0.00067
STAMP_TAX_RATE = 0.001


class TradeRecord(BaseModel):
    '''Single executed trade. ``trade_id`` is auto-generated.

    Commission is always computed at ``COMMISSION_RATE``.
    Stamp tax is only charged on SELL orders, computed as ``price * qty * STAMP_TAX_RATE``.
    Slippage is an optional estimated cost.
    '''
    trade_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], description='unique, auto-generated id')
    ticker: str
    side: Side
    price: float
    qty: int
    commission: float = Field(default=0.0, description='computed in post-processing hook')
    stamp_tax: float = Field(default=0.0, description='0 for BUY; price*qty*0.001 for SELL')
    slippage: float = Field(default=0.0)
    net_amount: float = 0.0
    portfolio_id: Optional[str] = Field(default=None, description='parent portfolio run id')
    signal_source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @staticmethod
    def compute_commission(price: float, qty: int) -> float:
        amount = price * qty * COMMISSION_RATE
        return max(1.0, round(amount, 2))

    @staticmethod
    def compute_stamp_tax(price: float, qty: int) -> float:
        return round(price * qty * STAMP_TAX_RATE, 2)

    model_config = {
        'extra': 'forbid'
    }
