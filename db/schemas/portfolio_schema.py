# Source Generated with Decompyle++
# File: portfolio_schema.cpython-311.pyc (Python 3.11)

'''Pydantic models for portfolio snapshots.'''
from __future__ import annotations
from datetime import date as DateType, datetime
from typing import Optional
from pydantic import BaseModel, Field

class PortfolioSnapshot(BaseModel):
    '''Periodic snapshot of the trading portfolio state (one row per date).'''
    _INITIAL_CASH: 'float' = 1e+06
    date: 'DateType | str' = Field(..., description = 'Snapshot date, YYYY-MM-DD')
    positions: 'dict[str, float]' = { }
    equity: 'float' = 0
    cash: 'float' = _INITIAL_CASH
    pnl: 'float' = 0
    benchmark_value: 'Optional[float]' = None
    created_at: 'datetime' = Field(default_factory = datetime.now)

