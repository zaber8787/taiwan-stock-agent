# File: app/server.py

'''
FastAPI Web Server providing REST APIs, background auto-trader, and pure monitoring GUI.
'''
from __future__ import annotations
import os
import asyncio
import logging
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from db.paper_trader import get_paper_trader
from db.mongo_client import check_mongo_status
from db.qdrant_manager import check_qdrant_status
from crawlers.yfinance_crawler import fetch_yahoo_stock_page
from crawlers.stock_scanner import get_stock_scanner
from crawlers.industry_graph import TAG_TO_COMPANIES
from app.news_listener import NewsEventListener, get_recent_news_events, get_listener_status, clear_recent_news_events
from app.scheduler import start_periodic_scheduler
from app.market_hours import is_market_open, get_market_status, is_call_auction_time
from app.watch_scheduler import get_watch_scheduler
from app.auto_trader import AutoTraderEngine, get_universe_status_cache, get_auto_trader_status
from app.news_listener import NewsEventListener, get_recent_news_events, get_listener_status, clear_recent_news_events, get_queue_status

logger = logging.getLogger(__name__)

app = FastAPI(title="Taiwan Stock Agent GUI", version="4.0.0")

_PAPER_TRADING_ENABLED = os.getenv('PAPER_TRADING_ENABLED', 'true').lower() == 'true'
_REAL_TRADING_ENABLED = os.getenv('REAL_TRADING_ENABLED', 'false').lower() == 'true'
_TRADING_API_URL = os.getenv('TRADING_API_URL', '')
_TRADING_API_KEY = os.getenv('TRADING_API_KEY', '')

_WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
if os.path.exists(_WEB_DIR):
    app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")


class ResetRequest(BaseModel):
    capital: float | None = 1000000.0


class TradeToggleRequest(BaseModel):
    mode: str  # 'paper' or 'real'
    enabled: bool


class StockAnalysisRequest(BaseModel):
    tickers: list[str]
    news_context: str | None = None


@app.post("/api/trade/toggle")
async def toggle_trading_mode(req: TradeToggleRequest):
    '''Toggle between paper and real trading mode.'''
    if req.mode not in ('paper', 'real'):
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'paper' or 'real'")
    
    if req.mode == 'paper':
        os.environ['PAPER_TRADING_ENABLED'] = 'true' if req.enabled else 'false'
        os.environ['REAL_TRADING_ENABLED'] = 'false'
    else:
        os.environ['REAL_TRADING_ENABLED'] = 'true' if req.enabled else 'false'
        os.environ['PAPER_TRADING_ENABLED'] = 'false'
    
    return {
        'message': f"Trading mode updated: {req.mode} trading {'enabled' if req.enabled else 'disabled'}",
        'paper_trading_enabled': os.getenv('PAPER_TRADING_ENABLED'),
        'real_trading_enabled': os.getenv('REAL_TRADING_ENABLED')
    }


@app.get("/api/stocks/analyze")
async def analyze_stocks(tickers: str, news_context: str | None = None):
    '''Batch analyze multiple stocks in parallel.'''
    if not tickers:
        raise HTTPException(status_code=400, detail="Missing 'tickers' query parameter")
    
    ticker_list = [t.strip() for t in tickers.split(',') if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No valid tickers provided")
    
    try:
        from agents.team import analyze_multiple_stocks
        results = await analyze_multiple_stocks(ticker_list, news_context)
        return {
            'count': len(results),
            'results': results
        }
    except Exception as e:
        logger.error(f"Stock analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/news/queue")
async def get_news_queue_status():
    '''Get current news analysis queue status.'''
    return get_queue_status()


@app.get("/api/trading-config")
async def get_trading_config():
    '''Get current trading configuration.'''
    return {
        'paper_trading_enabled': _PAPER_TRADING_ENABLED,
        'real_trading_enabled': _REAL_TRADING_ENABLED,
        'trading_api_url': _TRADING_API_URL if _TRADING_API_URL else '',
        'max_positions_limit': os.getenv('MAX_POSITIONS_LIMIT'),
        'max_single_stock_pct': os.getenv('MAX_SINGLE_STOCK_PCT'),
        'max_single_stock_lots': os.getenv('MAX_SINGLE_STOCK_LOTS'),
        'max_industry_pct': os.getenv('MAX_INDUSTRY_PCT'),
        'max_parallel_analysis': os.getenv('MAX_PARALLEL_ANALYSIS'),
        'analysis_queue_timeout': os.getenv('ANALYSIS_QUEUE_TIMEOUT')
    }


@app.on_event("startup")
async def on_startup():
    logger.info("🚀 [Server] 啟動背景全自動多標的 AI 交易引擎、觀察排程器與新聞監聽服務...")
    asyncio.create_task(start_periodic_scheduler())
    
    listener = NewsEventListener()
    asyncio.create_task(listener.start_listening_loop())

    auto_engine = AutoTraderEngine()
    asyncio.create_task(auto_engine.scan_and_trade_universe_loop())


@app.get("/", response_class=HTMLResponse)
async def serve_gui():
    index_path = os.path.join(_WEB_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>Taiwan Stock Agent Web GUI (Index file missing)</h2>")


@app.get("/api/account")
async def get_account_info():
    pt = get_paper_trader()
    holdings_tickers = list(pt.state.get('holdings', {}).keys())
    quotes = {}
    for t in holdings_tickers:
        res = await fetch_yahoo_stock_page(t)
        if res.get('success') and 'data' in res and 'price' in res['data']:
            if res['data']['price'] > 0:
                quotes[t] = res['data']['price']

    return pt.get_account_summary(price_quotes=quotes)


@app.get("/api/market-status")
async def get_market_status_info():
    status = get_market_status()
    return {
        "is_market_open": status['is_open'],
        "is_call_auction": status.get('is_call_auction', False),
        "current_time": status['current_time'],
        "seconds_until_next_open": status.get('seconds_to_open', 0),
        "seconds_until_close": status.get('seconds_to_close', 0),
        "status_text": "🟢 盤中交易中" if status['is_open'] else "🌙 非交易時段"
    }


@app.get("/api/watchlist")
async def get_watchlist():
    ws = get_watch_scheduler()
    return {"watchlist": ws.get_active_watchlist()}


@app.get("/api/autotrader/universe")
async def get_universe():
    return {"universe": get_universe_status_cache()}


@app.get("/api/autotrader/status")
async def autotrader_status():
    return get_auto_trader_status()


@app.get("/api/tags")
async def get_tags_info():
    return {"tags": TAG_TO_COMPANIES}


@app.get("/api/db-status")
async def get_db_status():
    return {
        "mongo": check_mongo_status(),
        "qdrant": check_qdrant_status()
    }


@app.get("/api/trades")
async def get_trade_logs():
    pt = get_paper_trader()
    return {"trades": list(reversed(pt.trades))}


@app.get("/api/listener/status")
async def listener_status():
    scanner = get_stock_scanner()
    status = get_listener_status()
    status['companies_in_db'] = len(scanner.companies_db)
    status['db'] = {
        'mongo': check_mongo_status(),
        'qdrant': check_qdrant_status()
    }
    return status


@app.get("/api/news-feed")
async def get_news_feed():
    return {"events": get_recent_news_events()}


@app.post("/api/reset")
async def reset_account(req: ResetRequest):
    pt = get_paper_trader()
    account = pt.reset_account(capital=req.capital)
    get_watch_scheduler().clear_watchlist()
    clear_recent_news_events()
    return {"message": "System fully reset (capital, holdings, trades, watchlists, events)", "account": account}


def start_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
