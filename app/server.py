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
from app.market_hours import is_market_open, get_seconds_until_next_market_open
from app.watch_scheduler import get_watch_scheduler
from app.auto_trader import AutoTraderEngine, get_universe_status_cache, get_auto_trader_status

logger = logging.getLogger(__name__)

app = FastAPI(title="Taiwan Stock Agent GUI", version="3.0.0")

_WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
if os.path.exists(_WEB_DIR):
    app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")


class ResetRequest(BaseModel):
    capital: float | None = 1000000.0


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
async def get_market_status():
    open_flag = is_market_open()
    next_seconds = get_seconds_until_next_market_open() if not open_flag else 0
    return {
        "is_market_open": open_flag,
        "seconds_until_next_open": next_seconds,
        "status_text": "🟢 盤中交易中" if open_flag else f"🌙 非交易時段 (距離開盤 {next_seconds // 3600}小時 {(next_seconds % 3600) // 60}分)"
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
