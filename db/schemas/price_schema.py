# File: db/schemas/price_schema.py

'''Pydantic models for price / OHLCV data.'''
from __future__ import annotations
from datetime import date as DateType, datetime
from typing import Optional, Union
from pydantic import BaseModel, Field


class CustomBaseModel(BaseModel):
    model_config = {
        'populate_by_name': True
    }


class DailyOHLCV(BaseModel):
    '''One trading-day bar for a ticker. Unique key: (ticker, date).'''
    date: Union[DateType, str]
    open: float
    high: float
    low: float
    close: float
    vol: float = Field(..., description='volume (shares)')
    turnover: Optional[float] = Field(default=None, description='turnover in TWD')
    source: str = ''

    model_config = {
        'extra': 'forbid'
    }


class PriceIndex(BaseModel):
    date: Union[DateType, str] = Field(default='Compact date index for price lookups.')
    doc_id: Optional[str] = Field(default=None, alias='_id', json_schema_extra={'bson_type': 'ObjectId'})

    model_config = {
        'populate_by_name': True
    }
