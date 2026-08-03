# File: db/__init__.py

'''Stock agent database layer — MongoDB + Qdrant vector store + Paper Trader.'''
from db.base_client import BaseDBClient
from db.mongo_client import MongoClient, get_mongo_client
from db.qdrant_manager import QdrantManager, get_qdrant_manager
from db.paper_trader import PaperTrader, get_paper_trader

try:
    from db.schemas import (
        CompanyProfile, CompanyIndex, DailyOHLCV, PriceIndex,
        NewsArticle, TradeRecord, Side, COMMISSION_RATE, STAMP_TAX_RATE, PortfolioSnapshot
    )
except ImportError:
    pass

__all__ = [
    'BaseDBClient',
    'MongoClient',
    'get_mongo_client',
    'QdrantManager',
    'get_qdrant_manager',
    'PaperTrader',
    'get_paper_trader'
]
