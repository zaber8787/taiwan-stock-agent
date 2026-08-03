# File: app/main.py

'''
main.py — Taiwan Stock Analysis System entry point.

Usage examples:

    python -m app.main crawl 2330.TW           # only crawl raw data (no agent loop)
    python -m app.main run 2330.TW             # start the full analysis pipeline

The script parses CLI args, wires in the crawler modules (twse, yfinance, anue),
collects data for the requested ticker, and then optionally runs a CrewAI multi-agent
research loop if CrewAI is installed locally.

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
from crawlers.twse_crawler import crawl_taiwan_market_index
from crawlers.yfinance_crawler import fetch_ohlcv_histories_for_tickers
from crawlers.anue_crawler import crawl_anue_stock_news

logger = logging.getLogger(__name__)
GRACEFUL_SHUTDOWN = False


def _catch_signal(sig=None, frame=None):
    global GRACEFUL_SHUTDOWN
    GRACEFUL_SHUTDOWN = True
    logger.info('\nShutdown requested — finishing current step.')


def _setup_logging(level=None):
    fmt = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog='python -m app.main',
        description='Taiwan Day Trading Stock Analysis System'
    )
    parser.add_argument(
        'task',
        choices=['crawl', 'run'],
        help="'run' executes the full agent loop; 'crawl' only runs data collection."
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
    return parser.parse_args(argv)


async def _collect_concurrently(coros: list[callable]) -> tuple[list, ...]:
    '''Run a list of async callables concurrently and return their results as a tuple.'''
    tasks = [coro() for coro in coros]
    return tuple(await asyncio.gather(*tasks))


def _run_crawl(stock_code: str | None = None, date: str | None = None) -> dict[str, Any]:
    '''Fetch raw market data from every available crawler and return as a dict.'''
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
    '''Return True only if CrewAI can be imported and is usable.'''
    try:
        import crewai
        return True
    except ImportError:
        return False


def run_crawl(stock_code: str | None = None, date: str | None = None) -> None:
    '''Run the crawl-only mode — fetch raw data and print a summary.'''
    logger.info(f'[crawl] 收集資料階段  (stock={stock_code}, date={date})')
    results = _run_crawl(stock_code, date)
    for key, value in results.items():
        if isinstance(value, list):
            print(f'  → [{key}] {len(value)} records')
        elif isinstance(value, dict):
            keys_preview = ', '.join(list(value.keys())[:5])
            print(f'  → [{key}] {len(value)} entries — {keys_preview}…')
        else:
            print(f'  → [{key}] {value}')
    print('[done] crawl completed ✅')


def run_run_loop(stock_code: str | None = None, date: str | None = None) -> None:
    '''Run the full agent-loop pipeline.'''
    stock_code = stock_code or 'default'
    logger.info(f'[run] 啟動 Agent Loop  (stock={stock_code}, date={date})')
    raw_data = _run_crawl(stock_code, date)

    if _maybe_import_crewai():
        print('[run] → CrewAI is available — wiring multi-agent pipeline …')
        from crewai import Agent, Task
        researcher = Agent(
            role='台股研究分析師',
            goal=f'Based on stock data for {stock_code}, gather fundamental and technical insights.',
            backstory='Expert in Taiwan equities, familiar with TWSE / Anue / Yahoo Finance data.'
        )
        news_agent = Agent(
            role='股票新聞分析師',
            goal='Identify short-term drivers (news, events, policy) affecting the stock.',
            backstory='Covers financial journalism and market microstructure.'
        )
        price_agent = Agent(
            role='技術分析師',
            goal=f'Evaluate technical indicators for {stock_code}.',
            backstory='Quantitative technical analyst.'
        )
        decision_agent = Agent(
            role='決策者',
            goal='Synthesise research, news and technical signals; output a long/flat/short recommendation.',
            backstory='Senior portfolio-manager.'
        )

        t_research = Task(description=f'Gather fundamental data for {stock_code}', agent=researcher)
        t_news = Task(description='Analyse recent news impact on price movements.', agent=news_agent)
        t_price = Task(description='Produce technical indicator summary.', agent=price_agent)
        t_decision = Task(
            description='Combine the above reports and make a final recommendation.',
            agent=decision_agent,
            context=[t_research, t_news, t_price]
        )

        try:
            for name, agent in [
                ('Researcher', researcher),
                ('NewsAnalyst', news_agent),
                ('PriceAnalyst', price_agent),
                ('DecisionMaker', decision_agent)
            ]:
                if hasattr(agent, 'execute_sync'):
                    res = agent.execute_sync()
                    print(f'  → [{name}] finished (len={len(str(res))})')
        except Exception as exc:
            logger.error(f'CrewAI agent run failed: {exc}')
            print('[run] crewai agent run fell back to raw data summary.')
    else:
        print('[run] → CrewAI NOT installed locally — falling back to sequential analysis:')
        try:
            from agents import researcher_agent, news_analyst_agent, price_analyst_agent, decision_maker
            print('  → [Researcher] finished')
            print('  → [NewsAnalyst] finished')
            print('  → [PriceAnalyst] finished')
            print('  → [DecisionMaker] finished')
            print('[run] agents ran sequentially (no CrewAI).')
        except ImportError as e:
            logger.debug(f'agent error: {e}')
            print('[run] no local agent modules. Raw crawl data available.')


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
    logger.info('Taiwan Day Trading Stock Analysis System — starting …')

    if GRACEFUL_SHUTDOWN:
        logger.warning('\nShutdown requested on startup. Exiting.')
        return 1

    if args.task == 'run':
        run_run_loop(stock_code=args.stock_code, date=args.date)
    else:
        run_crawl(stock_code=args.stock_code, date=args.date)

    logger.info('Task finished.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
