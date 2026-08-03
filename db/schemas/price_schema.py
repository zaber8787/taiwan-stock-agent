# Source Generated with Decompyle++
# File: price_schema.cpython-311.pyc (Python 3.11)

'''Pydantic models for price / OHLCV data.'''
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

class CustomBaseModel(BaseModel):
    model_config = {
        'populate_by_name': True }


class DailyOHLCV(BaseModel):
    '''One trading-day bar for a ticker. Unique key: (ticker, date).'''
    date: date | str = ...
    open: float = ...
    high: float = ...
    low: float = ...
    close: float = ...
    vol: float = Field(..., description = 'volume (shares)')
    turnover: Optional[float] = Field(default = None, description = 'turnover in TWD')
    source: str = ''
    
    class Config:
        extra = 'forbid'



class PriceIndex(BaseModel):
    date: date | str = 'Compact date index for price lookups.'
    doc_id: Optional[str] = Field(default = None, alias = '_id', json_schema_extra = {
        'bson_type': 'ObjectId' })
    model_config = {
        'populate_by_name': True }

