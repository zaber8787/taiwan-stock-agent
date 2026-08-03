# File: agents/tools/base.py

'''Base classes and interfaces for custom tools.'''
from __future__ import annotations
from typing import Any

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        name: str = ""
        description: str = ""
        def _run(self, *args, **kwargs) -> Any:
            raise NotImplementedError


class AbstractStockTool(BaseTool):
    '''Common ancestor for all custom stock tools.'''
    pass
