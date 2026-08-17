# File: agents/tools/base.py
"""
Base classes and interfaces for custom CrewAI tools.
Includes safe async-to-sync runner to avoid 'Event loop is already running' errors.
"""
from __future__ import annotations
import asyncio
import concurrent.futures
import threading
from typing import Any, Coroutine

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        name: str = ""
        description: str = ""
        def _run(self, *args, **kwargs) -> Any:
            raise NotImplementedError


def run_async_safely(coro: Coroutine) -> Any:
    """
    Safely execute an async coroutine from synchronous tool code,
    working correctly inside running event loops (FastAPI / CrewAI) and worker threads.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Inside an already running event loop: run in a dedicated background worker thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(coro))
            return future.result(timeout=30)
    else:
        return asyncio.run(coro)


class AbstractStockTool(BaseTool):
    """Common ancestor for all custom stock tools."""
    pass
