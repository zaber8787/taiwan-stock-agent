# File: crawlers/config.py

'''Crawler configuration — shared settings, default headers, delays (loads settings from .env).'''
from __future__ import annotations
import os
import random
import time
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class CrawlerConfig:
    '''Shared crawler runtime settings.'''
    scraping_delay_min: float = float(os.getenv('SCRAPING_DELAY_MIN', '1.0'))
    scraping_delay_max: float = float(os.getenv('SCRAPING_DELAY_MAX', '3.0'))
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    user_agent_str: str = os.getenv('USER_AGENT', 'Mozilla/5.0 (compatible; StockAgent/1.0; +https://stock-agent.ai)')

    @classmethod
    def user_agent(cls) -> str:
        return os.getenv('USER_AGENT', cls.user_agent_str)

    def random_delay(self) -> float:
        return random.uniform(self.scraping_delay_min, self.scraping_delay_max)

    def sleep(self) -> None:
        time.sleep(self.random_delay())


SOURCES = {
    'twse': 'https://www.twse.com.tw/zh/index.html',
    'yahoo_tw': 'https://tw.stock.yahoo.com/',
    'mops_foreign': 'https://mops.twse.com.tw/mops/web/t05sr01_1',
    'twse_fund_broker': 'https://www.twse.com.tw/zh/page/trading/fund/BFI82U.html',
    'anue': 'http://www.anue.com/',
    'changshang_times': 'https://www.ctsandp.com/',
    'ecb_newspaper': 'https://www.ebc.net.tw/',
    'ptt_stock': 'https://www.ptt.cc/bbs/Stock/index.html',
    'yfinance': None
}

INDUSTRY_TO_CRAWLERS = {
    '科技': ['yfinance', 'twse', 'anue', 'changshang_times', 'ecb_newspaper', 'ptt_stock'],
    '半導體': ['yfinance', 'twse', 'anue', 'changshang_times', 'ecb_newspaper', 'ptt_stock'],
    'AI': ['yfinance', 'twse', 'anue', 'changshang_times', 'ecb_newspaper', 'ptt_stock'],
    '電動車': ['yfinance', 'twse', 'anue', 'ctsandp', 'ecb_newspaper', 'ptt_stock'],
    '綠能': ['yfinance', 'twse', 'anue', 'changshang_times', 'ptt_stock']
}
