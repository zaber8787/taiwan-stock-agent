# File: db/schemas/company_schema.py

'''Pydantic models for company data with Multi-Tag support.'''
from __future__ import annotations
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    '''Full company profile document. Primary key: ``ticker``.'''
    description: str = Field(default="", description="Stock ticker or description (e.g. '2330')")
    tags: list[str] = Field(default_factory=list, description="Concept tags ['半導體', 'AI', 'CoWoS']")
    products: list[dict] = Field(default_factory=list)
    subsidiaries: list[dict] = Field(default_factory=list)
    marketCap: Optional[float] = Field(default=None, description='Market cap in TWD millions')
    employees: Optional[int] = Field(default=None)
    source: str = ''
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1, description='Auto-incremented on each update')

    model_config = {
        'extra': 'forbid'
    }


class CompanyIndex(BaseModel):
    industry: str = 'Compact lookup index — one document per ticker.'
    model_config = {
        'extra': 'allow'
    }
