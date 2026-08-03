# File: crawlers/stock_scanner.py

'''
Stock & ETF Universe Scanner & Auto Ingestion Manager.
Scans Taiwan Tech Stocks & ETFs, checks DB, performs deep profile lookup, and ingests missing data with multi-tags.
'''
from __future__ import annotations
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Any

from crawlers.yfinance_crawler import fetch_yahoo_stock_page, fetch_ohlcv_histories_for_tickers
from crawlers.mops_crawler import crawl_mops_financial_statement

logger = logging.getLogger(__name__)

_LOCAL_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
_COMPANIES_FILE = os.path.join(_LOCAL_DATA_DIR, 'companies.json')

# Tech Stocks & ETFs Universe with Multi-Tag Metadata
TARGET_UNIVERSE = [
    # Semiconductors & Foundry
    {'ticker': '2330.TW', 'name': '台積電', 'category': '半導體', 'tags': ['半導體', '晶圓代工', 'AI', 'CoWoS', '先進封裝', '權值股']},
    {'ticker': '2454.TW', 'name': '聯發科', 'category': '半導體IC設計', 'tags': ['半導體', 'IC設計', 'AI', '手機晶片']},
    {'ticker': '2303.TW', 'name': '聯電', 'category': '半導體晶圓代工', 'tags': ['半導體', '晶圓代工', '成熟製程']},
    {'ticker': '3034.TW', 'name': '聯詠', 'category': '半導體IC設計', 'tags': ['半導體', 'IC設計', '驅動IC']},
    {'ticker': '2379.TW', 'name': '瑞昱', 'category': '半導體網通IC', 'tags': ['半導體', 'IC設計', '網通IC']},
    {'ticker': '3443.TW', 'name': '創意', 'category': 'IP/ASIC', 'tags': ['半導體', 'IP', 'ASIC', 'AI']},
    {'ticker': '3661.TW', 'name': '世芯-KY', 'category': 'IP/ASIC', 'tags': ['半導體', 'IP', 'ASIC', 'AI']},

    # Memory
    {'ticker': '2408.TW', 'name': '南亞科', 'category': '記憶體', 'tags': ['記憶體', 'DRAM', '半導體', 'AI']},
    {'ticker': '2344.TW', 'name': '華邦電', 'category': '記憶體', 'tags': ['記憶體', 'DRAM', 'Flash', '半導體']},
    {'ticker': '8299.TW', 'name': '群聯', 'category': '記憶體', 'tags': ['記憶體', 'NAND', '控制晶片', 'AI']},
    
    # AI Servers & Systems
    {'ticker': '2382.TW', 'name': '廣達', 'category': 'AI伺服器/電腦', 'tags': ['AI', 'AI伺服器', '代工', '筆電', '雲端']},
    {'ticker': '3231.TW', 'name': '緯創', 'category': 'AI伺服器/代工', 'tags': ['AI', 'AI伺服器', '代工', '雲端']},
    {'ticker': '2317.TW', 'name': '鴻海', 'category': '組裝代工/電動車', 'tags': ['AI', 'AI伺服器', '組裝', '電動車', '蘋果']},
    {'ticker': '2376.TW', 'name': '技嘉', 'category': 'AI伺服器/主機板', 'tags': ['AI', 'AI伺服器', '主機板', '電競']},
    {'ticker': '2356.TW', 'name': '英業達', 'category': 'AI伺服器', 'tags': ['AI', 'AI伺服器', '代工']},
    {'ticker': '2377.TW', 'name': '微星', 'category': '電競/主機板', 'tags': ['電競', '主機板', '顯示卡']},
    
    # Cooling & Power Components
    {'ticker': '3017.TW', 'name': '奇鋐', 'category': '散熱模組', 'tags': ['散熱', 'AI伺服器散熱', '水冷', '電子零組件']},
    {'ticker': '3324.TW', 'name': '雙鴻', 'category': '散熱模組', 'tags': ['散熱', 'AI伺服器散熱', '水冷', '電子零組件']},
    {'ticker': '2308.TW', 'name': '台達電', 'category': '電源/綠能/AI電源', 'tags': ['電源', 'AI電源', '綠能', '電動車']},

    # Optics
    {'ticker': '3008.TW', 'name': '大立光', 'category': '光學鏡頭', 'tags': ['光學鏡頭', '蘋果', '手機零組件']},

    # Popular High-Dividend & Tech ETFs
    {'ticker': '0050.TW', 'name': '元大台灣50', 'category': '市值型ETF', 'tags': ['ETF', '市值型', '權值股']},
    {'ticker': '0056.TW', 'name': '元大高股息', 'category': '高股息ETF', 'tags': ['ETF', '高股息', '永續']},
    {'ticker': '00878.TW', 'name': '國泰永續高股息', 'category': '高股息ETF', 'tags': ['ETF', '高股息', '永續']},
    {'ticker': '00919.TW', 'name': '群益台灣精選高息', 'category': '高股息ETF', 'tags': ['ETF', '高股息']},
    {'ticker': '00929.TW', 'name': '復華台灣科技優息', 'category': '科技高股息ETF', 'tags': ['ETF', '高股息', '科技高股息', '半導體']},
    {'ticker': '00940.TW', 'name': '元大台灣價值高息', 'category': '高股息ETF', 'tags': ['ETF', '高股息']}
]


class StockScanner:
    '''Scans universe, checks MongoDB/JSON, and auto-ingests deep profile data.'''

    def __init__(self) -> None:
        os.makedirs(_LOCAL_DATA_DIR, exist_ok=True)
        self.companies_db: dict[str, dict[str, Any]] = self._load_local_companies()

    def _load_local_companies(self) -> dict[str, dict[str, Any]]:
        if os.path.exists(_COMPANIES_FILE):
            try:
                with open(_COMPANIES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load local companies JSON: {e}")
        return {}

    def _save_local_companies(self) -> None:
        try:
            with open(_COMPANIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.companies_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save local companies JSON: {e}")

    async def scan_and_ingest_all(self, force_update: bool = False) -> dict[str, Any]:
        '''Scan universe, check DB for missing items, fetch profile & ingest.'''
        logger.info("🔍 [StockScanner] 啟動台股科技股與 ETF 全自動掃描與建檔...")
        ingested_count = 0
        updated_count = 0

        for item in TARGET_UNIVERSE:
            ticker = item['ticker']
            clean_code = ticker.replace('.TW', '')

            exists_in_mongo = False
            try:
                from db.mongo_client import get_mongo_client
                mc = get_mongo_client()
                doc = mc.find_one('companies', {'ticker': clean_code})
                if doc:
                    exists_in_mongo = True
            except Exception:
                pass

            exists_in_local = clean_code in self.companies_db

            if not exists_in_mongo and not exists_in_local or force_update:
                logger.info(f"📥 [StockScanner] 發現新標的/缺檔標的: {ticker} ({item['name']}) -> 執行深度爬取與多標籤建檔...")
                profile = await self._deep_ingest_stock(ticker, item)
                
                self.companies_db[clean_code] = profile
                self._save_local_companies()

                try:
                    from db.mongo_client import get_mongo_client
                    mc = get_mongo_client()
                    mc.update_one('companies', {'ticker': clean_code}, {'$set': profile}, upsert=True)
                except Exception:
                    pass

                ingested_count += 1
            else:
                updated_count += 1

        logger.info(f"✅ [StockScanner] 掃描完成！新建檔: {ingested_count} 家，已有庫存資料: {updated_count} 家")
        return {
            'total_universe': len(TARGET_UNIVERSE),
            'newly_ingested': ingested_count,
            'existing_in_db': len(self.companies_db),
            'items': list(self.companies_db.values())
        }

    async def _deep_ingest_stock(self, ticker: str, meta: dict[str, Any]) -> dict[str, Any]:
        clean_code = ticker.replace('.TW', '')
        yf_res = await fetch_yahoo_stock_page(clean_code)
        yf_data = yf_res.get('data', {}) if yf_res.get('success') else {}
        mops_res = await crawl_mops_financial_statement(clean_code)

        profile = {
            'ticker': clean_code,
            'full_ticker': ticker,
            'name': meta['name'],
            'category': meta['category'],
            'tags': meta.get('tags', [meta['category']]),
            'current_price': yf_data.get('price', 0.0),
            'pe_ratio': yf_data.get('pe_ratio', 'N/A'),
            'eps': mops_res.get('eps', 'N/A') if isinstance(mops_res, dict) else 'N/A',
            'market_cap': yf_data.get('market_cap', 'N/A'),
            'summary': f"{meta['name']} ({clean_code}) — 產業: {meta['category']} | 標籤: {', '.join(meta.get('tags', []))}",
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        return profile

    def get_known_tickers(self) -> list[str]:
        return list(set(list(self.companies_db.keys()) + [item['ticker'].replace('.TW', '') for item in TARGET_UNIVERSE]))


def get_stock_scanner() -> StockScanner:
    return StockScanner()
