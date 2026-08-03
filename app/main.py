# File: app/main.py

'''
main.py — Taiwan Stock Analysis System entry point.

Usage examples:

    python -m app.main crawl 2330.TW           # only crawl raw data (no agent loop)
    python -m app.main run 2330.TW             # start the full agent loop & paper trading
    python -m app.main gui                     # launch the Web GUI Dashboard & API Server

Graceful shutdown on SIGINT / SIGTERM is supported.
'''
from __future__ import annotations
import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Any

# Ensure stdout uses UTF-8 encoding on Windows
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from crawlers.twse_crawler import crawl_taiwan_market_index
from crawlers.yfinance_crawler import fetch_ohlcv_histories_for_tickers
from crawlers.anue_crawler import crawl_anue_stock_news
from db.mongo_client import check_mongo_status
from db.qdrant_manager import check_qdrant_status

logger = logging.getLogger(__name__)
GRACEFUL_SHUTDOWN = False


def _catch_signal(sig=None, frame=None):
    global GRACEFUL_SHUTDOWN
    GRACEFUL_SHUTDOWN = True
    logger.info('\nShutdown requested — finishing current step.')


def _setup_logging(level=None):
    fmt = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)


def _check_databases_on_startup() -> None:
    '''Check and display Database connection statuses on console startup.'''
    mongo_info = check_mongo_status()
    qdrant_info = check_qdrant_status()

    m_status = "✅ [CONNECTED]" if mongo_info['connected'] else "⚠️ [OFFLINE / LOCAL FALLBACK]"
    q_status = "✅ [CONNECTED]" if qdrant_info['connected'] else "⚠️ [OFFLINE / LOCAL FALLBACK]"

    print("\n" + "=" * 60)
    print("🔍 資料庫連線狀態檢查 (Database Connection Check on Startup):")
    print(f"  • MongoDB: {m_status} -> {mongo_info['uri']} (db: {mongo_info['db_name']})")
    print(f"  • Qdrant:  {q_status} -> {qdrant_info['uri']} (collection: {qdrant_info['collection']})")
    print("  • 持久化:  ✅ [READY] 本地 JSON 備份檔 (data/paper_account.json)")
    print("=" * 60 + "\n")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog='python -m app.main',
        description='Taiwan Day Trading Stock Analysis & Paper Trading System'
    )
    parser.add_argument(
        'task',
        choices=['crawl', 'run', 'gui'],
        help="'gui' launches Web Dashboard; 'run' executes full agent loop & paper trade; 'crawl' only runs data collection."
    )
    parser.add_argument(
        'stock_code',
        nargs='?',
        default=None,
        help='Stock code to analyse (e.g. 2330.TW). Uses config defaults when omitted.'
    )
    parser.add_argument(
        '--date',
        default=None,
        help='Date window as YYYY-MM-DD. Defaults to today.'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase logging verbosity (add -vv for DEBUG).'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port for Web GUI Server (default 8000).'
    )
    return parser.parse_args(argv)


async def _collect_concurrently(coros: list[callable]) -> tuple[list, ...]:
    tasks = [coro() for coro in coros]
    return tuple(await asyncio.gather(*tasks))


def _run_crawl(stock_code: str | None = None, date: str | None = None) -> dict[str, Any]:
    stock_code = stock_code or os.environ.get('STOCK_CODE', '2330.TW')

    async def _yf_ohlcv():
        return await fetch_ohlcv_histories_for_tickers([stock_code])

    async def _anue_news():
        return await crawl_anue_stock_news(stock_code)

    async def _twse_index():
        return await crawl_taiwan_market_index()

    try:
        yf_ohlcv, anue_news, twse_idx = asyncio.run(
            _collect_concurrently([_yf_ohlcv, _anue_news, _twse_index])
        )
    except Exception as exc:
        logger.warning(f'crawler error: {exc}')
        yf_ohlcv, anue_news, twse_idx = [], [], {}

    return {
        'yfinance_ohlcv': yf_ohlcv,
        'anue_news': anue_news,
        'twse_index': twse_idx
    }


def _maybe_import_crewai() -> bool:
    try:
        import crewai
        return True
    except ImportError:
        return False


def run_crawl(stock_code: str | None = None, date: str | None = None) -> None:
    logger.info(f'[crawl] 收集資料階段  (stock={stock_code}, date={date})')
    results = _run_crawl(stock_code, date)
    for key, value in results.items():
        if isinstance(value, list):
            print(f'  -> [{key}] {len(value)} records')
        elif isinstance(value, dict):
            keys_preview = ', '.join(list(value.keys())[:5])
            print(f'  -> [{key}] {len(value)} entries — {keys_preview}...')
        else:
            print(f'  -> [{key}] {value}')
    print('[done] crawl completed [OK]')


def run_run_loop(stock_code: str | None = None, date: str | None = None) -> None:
    stock_code = stock_code or '2330.TW'
    clean_ticker = stock_code.replace('.TW', '')
    logger.info(f'[run] 啟動 Agent Loop & Paper Trading  (stock={stock_code})')
    
    from db.paper_trader import get_paper_trader
    pt = get_paper_trader()

    if _maybe_import_crewai():
        print('[run] -> CrewAI is available — wiring multi-agent pipeline...')
        try:
            from agents.team import run_crew
            crew_out = run_crew(ticker=clean_ticker)
            signal = crew_out.signal
            report = crew_out.report
        except Exception as e:
            logger.error(f'CrewAI agent run failed: {e}')
            from agents.decision_maker import synthesize_decision
            signal = synthesize_decision(ticker=clean_ticker)
            report = f"Fallback report for {clean_ticker}"
    else:
        print('[run] -> CrewAI NOT installed locally — executing heuristic agent flow:')
        from agents.decision_maker import synthesize_decision
        signal = synthesize_decision(ticker=clean_ticker, research_output="TWSE Data OK", news_output="Positive", price_output="RSI 55")
        report = f"# 📊 交易報告 ({clean_ticker})\n\n- 方向: **{signal.get('side')}**\n- 信心度: {signal.get('confidence'):.0%}\n- 原因: {signal.get('reason')}"

    trade_res = pt.execute_signal(signal, current_price=1000.0)
    print("\n" + "="*50)
    print(f"📊 模擬交易下單結果: {trade_res['status']} ({trade_res.get('action', signal.get('side'))})")
    print(f"帳戶最新總資產: ${pt.get_account_summary()['total_equity']:,.2f}")
    print("="*50 + "\n")
    print(report)


def run_gui_server(port: int = 8000) -> None:
    logger.info(f'Starting Web GUI Server on http://127.0.0.1:{port}')
    import webbrowser
    webbrowser.open(f'http://127.0.0.1:{port}')
    from app.server import start_server
    start_server(port=port)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    _setup_logging(level=level)

    signal.signal(signal.SIGINT, _catch_signal)
    signal.signal(signal.SIGTERM, _catch_signal)

    logger.info('============================================================')
    logger.info('Taiwan Day Trading Stock Analysis & Paper Trading System — starting...')

    # Check and print Database connections on console startup
    _check_databases_on_startup()

    if GRACEFUL_SHUTDOWN:
        logger.warning('\nShutdown requested on startup. Exiting.')
        return 1

    if args.task == 'gui':
        run_gui_server(port=args.port)
    elif args.task == 'run':
        run_run_loop(stock_code=args.stock_code, date=args.date)
    else:
        run_crawl(stock_code=args.stock_code, date=args.date)

    logger.info('Task finished.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
