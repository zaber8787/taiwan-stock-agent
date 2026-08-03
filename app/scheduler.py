# File: app/scheduler.py

'''
Periodic Task Scheduler for Taiwan Stock Agent.
Handles periodic refresh of DB company profiles & historical prices.
'''
from __future__ import annotations
import os
import asyncio
import logging
from crawlers.stock_scanner import get_stock_scanner

logger = logging.getLogger(__name__)

_REFRESH_INTERVAL_HOURS = int(os.getenv('DATA_REFRESH_INTERVAL_HOURS', '24'))


async def start_periodic_scheduler() -> None:
    '''Periodically refresh stock database profiles.'''
    scanner = get_stock_scanner()
    interval_seconds = _REFRESH_INTERVAL_HOURS * 3600

    # Initial scan on startup
    try:
        await scanner.scan_and_ingest_all(force_update=False)
    except Exception as e:
        logger.warning(f"Startup stock scanner error: {e}")

    while True:
        await asyncio.sleep(interval_seconds)
        logger.info(f"⏰ [Scheduler] 執行定時資料更新 (每 {_REFRESH_INTERVAL_HOURS} 小時)...")
        try:
            await scanner.scan_and_ingest_all(force_update=True)
        except Exception as e:
            logger.warning(f"Periodic scheduler error: {e}")
