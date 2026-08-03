# File: agents/config.py

'''Configuration helpers for agents & tools.'''
from __future__ import annotations
import functools
from pathlib import Path
from typing import Any
import yaml

_HERE = Path(__file__).resolve().parent
_CFG_DIR = _HERE.parent / 'config'
_DEFAULT_LLM: dict[str, Any] = {
    'model': 'qwen2.5:7b',
    'base_url': 'http://ollama:11434/v1',
    'temperature': 0.3,
    'max_tokens': 2000
}

try:
    from crewai import Tool
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False

    class Tool:
        def __init__(self, name: str, func: Any, description: str = "") -> None:
            self.name = name
            self.func = func
            self.description = description


def load_llm_cfg(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else _CFG_DIR / 'llm.yaml'
    out = dict(_DEFAULT_LLM)
    if cfg_path.exists():
        with open(cfg_path, 'r', encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
            if isinstance(data, dict):
                out.update(data)
    return out


def merge_agent_llm(agent_name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = load_llm_cfg()
    if cfg and isinstance(cfg, dict):
        agents_cfg = cfg.get('agents', {})
        if agent_name in agents_cfg:
            merged.update(agents_cfg[agent_name])
    return merged


def llm_for_crewai() -> dict[str, Any]:
    base_cfg = load_llm_cfg()
    return {
        'model': base_cfg.get('model', 'qwen2.5:7b'),
        'temperature': base_cfg.get('temperature', 0.3),
        'max_tokens': base_cfg.get('max_tokens', 2000),
        'base_url': base_cfg.get('base_url', 'http://ollama:11434/v1')
    }


def tools_for_category(cat: str = 'research') -> list[Tool]:
    '''Return the [RESEARCHER|ANALYST|DECISION] tool group.'''
    from agents.tools.research_tools import CrawlNewsForIndustry, FetchForeignInvestors, FetchPTTSentiment, FetchStockPrices
    from agents.tools.analyst_tools import CompanyProfileLookup, SentimentScorer, TechnicalAnalysis, VectorSearchNews
    from agents.tools.decision_tools import FinalPortfolioCheck, generate_trade_report

    groups = {
        'research': [
            Tool(name='FetchStockPrices', func=FetchStockPrices, description='Fetch stock prices'),
            Tool(name='FetchForeignInvestors', func=FetchForeignInvestors, description='Fetch institutional investors'),
            Tool(name='CrawlNewsForIndustry', func=CrawlNewsForIndustry, description='Crawl news for industry'),
            Tool(name='FetchPTTSentiment', func=FetchPTTSentiment, description='Fetch PTT sentiment')
        ],
        'analyst': [
            Tool(name='VectorSearchNews', func=VectorSearchNews, description='Search for similar news in Qdrant embeddings.'),
            Tool(name='CompanyProfileLookup', func=CompanyProfileLookup, description='Look up a company profile / info by ticker.'),
            Tool(name='TechnicalAnalysis', func=TechnicalAnalysis, description='Compute RSI, MACD, Bollinger Bands, SMA20/SMA60, etc.'),
            Tool(name='SentimentScorer', func=SentimentScorer, description='A simple lexicon-based sentiment scorer.')
        ],
        'decision': [
            Tool(name='FinalPortfolioCheck', func=FinalPortfolioCheck, description='Read the current portfolio holdings, cash, and equity.'),
            Tool(name='GenerateTradeReport', func=generate_trade_report, description='Assemble a final trade-report markdown.')
        ]
    }
    return groups.get(cat.lower(), groups['research'])
