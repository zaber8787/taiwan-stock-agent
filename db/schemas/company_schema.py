# Source Generated with Decompyle++
# File: company_schema.cpython-311.pyc (Python 3.11)

'''Pydantic models for company data.'''
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field

class CompanyProfile(BaseModel):
    '''Full company profile document. Primary key: ``ticker``.'''
    description: str = Field(..., description = "Stock ticker (e.g. '2330')")
    products: list[dict] = []
    subsidiaries: list[dict] = []
    marketCap: Optional[float] = Field(default = None, description = 'Market cap in TWD millions')
    employees: Optional[int] = Field(default = None)
    source: str = ''
    crawled_at: datetime = Field(default_factory = datetime.utcnow)
    updated_at: datetime = Field(default_factory = datetime.utcnow)
    version: int = Field(default = 1, description = 'Auto-incremented on each update')
    
    class Config:
        extra = 'forbid'



class CompanyIndex(BaseModel):
    industry: str = 'Compact lookup index — one document per ticker.'
    model_config = {
        'extra': 'allow' }

