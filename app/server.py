# File: app/server.py

'''
FastAPI Web Server providing REST APIs, background event listeners, and GUI frontend.
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
from crawlers.yfinance_crawler import fetch_yahoo_stock_page
from crawlers.stock_scanner import get_stock_scanner
from app.news_listener import NewsEventListener, get_recent_news_events, get_listener_status
from app.scheduler import start_periodic_scheduler

logger = logging.getLogger(__name__)

app = FastAPI(title="Taiwan Stock Agent GUI", version="1.0.0")

_WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
if os.path.exists(_WEB_DIR):
    app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")


class AnalyzeRequest(BaseModel):
    stock_code: str = "2330.TW"
    date: str | None = None


class ResetRequest(BaseModel):
    capital: float | None = 1000000.0


class AllocationRequest(BaseModel):
    ticker: str = "2330"
    price: float = 1000.0
    confidence: float = 0.8


@app.on_event("startup")
async def on_startup():
    '''Start background scanner, periodic scheduler & real-time news listener.'''
    logger.info("🚀 [Server] 啟動背景全自動監聽器與科技股/ETF 排程更新服務...")
    asyncio.create_task(start_periodic_scheduler())
    
    listener = NewsEventListener()
    asyncio.create_task(listener.start_listening_loop())


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


@app.get("/api/trades")
async def get_trade_logs():
    pt = get_paper_trader()
    return {"trades": list(reversed(pt.trades))}


@app.get("/api/listener/status")
async def listener_status():
    scanner = get_stock_scanner()
    status = get_listener_status()
    status['companies_in_db'] = len(scanner.companies_db)
    return status


@app.get("/api/news-feed")
async def get_news_feed():
    return {"events": get_recent_news_events()}


@app.post("/api/allocation-preview")
async def preview_allocation(req: AllocationRequest):
    pt = get_paper_trader()
    return pt.calculate_allocation(
        ticker=req.ticker,
        current_price=req.price,
        confidence=req.confidence
    )


@app.post("/api/analyze")
async def run_ai_analysis_and_trade(req: AnalyzeRequest):
    stock_code = req.stock_code.strip().upper()
    if not stock_code:
        raise HTTPException(status_code=400, detail="stock_code is required")

    pt = get_paper_trader()

    # 1. Fetch current price
    clean_ticker = stock_code.replace('.TW', '')
    quote_res = await fetch_yahoo_stock_page(clean_ticker)
    current_price = 1000.0
    if quote_res.get('success') and 'data' in quote_res and quote_res['data'].get('price'):
        current_price = quote_res['data']['price']

    # 2. Run AI agent flow or fallback
    try:
        from agents.team import run_crew
        crew_out = run_crew(ticker=clean_ticker)
        signal = crew_out.signal
        report = crew_out.report
        summary = crew_out.summary
    except Exception as e:
        logger.warning(f"CrewAI run fallback: {e}")
        from agents.decision_maker import synthesize_decision
        signal = synthesize_decision(ticker=clean_ticker, research_output="TWSE Data OK", news_output="Positive", price_output="RSI 55")
        report = f"# 📊 交易報告 ({clean_ticker})\n\n- 方向: **{signal.get('side')}**\n- 信心度: {signal.get('confidence'):.0%}\n- 原因: {signal.get('reason')}"
        summary = f"## {clean_ticker} 交易結論\n- **方向**: {signal.get('side')}\n- **原因**: {signal.get('reason')}"

    if not signal.get('ticker'):
        signal['ticker'] = clean_ticker
    if not signal.get('price_target'):
        signal['price_target'] = current_price

    alloc_info = pt.calculate_allocation(
        ticker=clean_ticker,
        current_price=current_price,
        confidence=float(signal.get('confidence', 0.5))
    )

    trade_result = pt.execute_signal(signal=signal, current_price=current_price)

    return {
        "stock_code": stock_code,
        "current_price": current_price,
        "signal": signal,
        "allocation_preview": alloc_info,
        "trade_execution": trade_result,
        "report_markdown": report,
        "summary_markdown": summary,
        "account": pt.get_account_summary()
    }


@app.post("/api/reset")
async def reset_account(req: ResetRequest):
    pt = get_paper_trader()
    account = pt.reset_account(capital=req.capital)
    return {"message": "Account reset successfully", "account": account}


def start_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
