# File: agents/config.py

'''Configuration helpers for agents & tools (loads settings from .env).'''
from __future__ import annotations
import os
import functools
from pathlib import Path
from typing import Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_HERE = Path(__file__).resolve().parent
_CFG_DIR = _HERE.parent / 'config'

def get_env_str(key: str, default: str) -> str:
    return os.getenv(key, default) or default

def get_env_float(key: str, default: float) -> float:
    try:
        val = os.getenv(key)
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default

def get_env_int(key: str, default: int) -> int:
    try:
        val = os.getenv(key)
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def load_llm_cfg(path: Path | str | None = None) -> dict[str, Any]:
    '''Load default LLM configuration combining .env variables and optional YAML file.'''
    cfg_path = Path(path) if path else _CFG_DIR / 'llm.yaml'
    out = {
        'model': get_env_str('LLM_MODEL', 'qwen2.5:7b'),
        'base_url': get_env_str('LLM_BASE_URL', 'http://localhost:11434/v1'),
        'temperature': get_env_float('LLM_TEMPERATURE', 0.3),
        'max_tokens': get_env_int('LLM_MAX_TOKENS', 2000)
    }
    if HAS_YAML and cfg_path.exists():
        with open(cfg_path, 'r', encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
            if isinstance(data, dict):
                out.update(data)
    return out


def get_llm_model_for_agent(agent_name: str | None = None) -> str:
    '''Resolve the target LLM model string for a given agent.'''
    if agent_name:
        env_key = f"{agent_name.upper().replace('-', '_')}_MODEL"
        override = os.getenv(env_key)
        if override:
            return override
    return get_env_str('LLM_MODEL', 'qwen2.5:7b')


def llm_for_crewai(agent_name: str | None = None) -> Any:
    '''Return LLM configuration or object suitable for CrewAI Agent.'''
    model_name = get_llm_model_for_agent(agent_name)
    base_cfg = load_llm_cfg()
    
    # Try importing CrewAI LLM wrapper if available
    try:
        from crewai import LLM
        api_key = os.getenv('OPENAI_API_KEY') or os.getenv('LLM_API_KEY') or 'NA'
        base_url = base_cfg.get('base_url')
        return LLM(
            model=model_name,
            base_url=base_url,
            temperature=base_cfg.get('temperature', 0.3),
            api_key=api_key
        )
    except Exception:
        # Fallback to string representation for CrewAI or custom runner
        return model_name


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
