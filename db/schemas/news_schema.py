# Source Generated with Decompyle++
# File: news_schema.cpython-311.pyc (Python 3.11)

'''Pydantic models for news/article data.'''
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class NewsArticle(BaseModel):
    '''Full news article document stored in MongoDB ``news`` collection.'''
    id: str = Field(default_factory = (lambda : uuid.uuid4().hex[:12]), description = 'Auto-generated short hex id')
    title: str = ...
    content: str = Field(default = '', description = 'full article body')
    source: str = Field(default = None, description = 'LLM-generated short summary')
    url: str = ''
    published_at: datetime = Field(..., description = 'article original publish time')
    crawled_at: datetime = Field(default_factory = datetime.utcnow)
    stock_codes: list[str] = Field(default_factory = list, description = "tag-like ticker codes ['2330', '2454']")
    industry: Optional[str] = None
    raw: Optional[dict] = Field(default = None, description = 'original JSON / HTML document if preserved')
    
    class Config:
        extra = 'forbid'


