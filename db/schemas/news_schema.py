# File: db/schemas/news_schema.py

'''Pydantic models for news/article data.'''
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    '''Full news article document stored in MongoDB ``news`` collection.'''
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], description='Auto-generated short hex id')
    title: str
    content: str = Field(default='', description='full article body')
    source: Optional[str] = Field(default=None, description='LLM-generated short summary or source')
    url: str = ''
    published_at: datetime = Field(default_factory=datetime.utcnow, description='article original publish time')
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    stock_codes: list[str] = Field(default_factory=list, description="tag-like ticker codes ['2330', '2454']")
    industry: Optional[str] = None
    raw: Optional[dict] = Field(default=None, description='original JSON / HTML document if preserved')

    model_config = {
        'extra': 'forbid'
    }
