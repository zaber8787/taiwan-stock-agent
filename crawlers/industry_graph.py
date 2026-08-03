# File: crawlers/industry_graph.py

'''
Taiwan Stock Supply Chain Industry Graph & Tag-Based Concept Filter.
Extracts concept tags from news text, maps industry supply chains,
and filters top-weighted stocks to prevent LLM Rate-Limit bottlenecks.
'''
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Taiwan Industry Supply Chain & Tag Mappings
TAG_TO_COMPANIES: dict[str, list[dict[str, Any]]] = {
    'AI': [
        {'ticker': '2330', 'weight': 1.0, 'name': '台積電'},
        {'ticker': '2382', 'weight': 1.0, 'name': '廣達'},
        {'ticker': '3231', 'weight': 0.9, 'name': '緯創'},
        {'ticker': '2317', 'weight': 0.9, 'name': '鴻海'},
        {'ticker': '2376', 'weight': 0.8, 'name': '技嘉'},
        {'ticker': '2454', 'weight': 0.8, 'name': '聯發科'},
    ],
    '半導體': [
        {'ticker': '2330', 'weight': 1.0, 'name': '台積電'},
        {'ticker': '2454', 'weight': 1.0, 'name': '聯發科'},
        {'ticker': '2303', 'weight': 0.8, 'name': '聯電'},
        {'ticker': '3034', 'weight': 0.7, 'name': '聯詠'},
        {'ticker': '3443', 'weight': 0.7, 'name': '創意'},
    ],
    '記憶體': [
        {'ticker': '2408', 'weight': 1.0, 'name': '南亞科'},
        {'ticker': '2344', 'weight': 1.0, 'name': '華邦電'},
        {'ticker': '8299', 'weight': 0.9, 'name': '群聯'},
    ],
    '散熱': [
        {'ticker': '3017', 'weight': 1.0, 'name': '奇鋐'},
        {'ticker': '3324', 'weight': 1.0, 'name': '雙鴻'},
    ],
    '電源': [
        {'ticker': '2308', 'weight': 1.0, 'name': '台達電'},
    ],
    'CoWoS': [
        {'ticker': '2330', 'weight': 1.0, 'name': '台積電'},
    ],
    'ETF': [
        {'ticker': '0050', 'weight': 1.0, 'name': '元大台灣50'},
        {'ticker': '0056', 'weight': 0.9, 'name': '元大高股息'},
        {'ticker': '00878', 'weight': 0.9, 'name': '國泰永續高股息'},
        {'ticker': '00919', 'weight': 0.9, 'name': '群益台灣精選高息'},
        {'ticker': '00929', 'weight': 1.0, 'name': '復華台灣科技優息'},
        {'ticker': '00940', 'weight': 0.8, 'name': '元大台灣價值高息'},
    ],
    '高股息': [
        {'ticker': '00929', 'weight': 1.0, 'name': '復華台灣科技優息'},
        {'ticker': '00878', 'weight': 1.0, 'name': '國泰永續高股息'},
        {'ticker': '00919', 'weight': 1.0, 'name': '群益台灣精選高息'},
        {'ticker': '0056', 'weight': 0.9, 'name': '元大高股息'},
    ]
}


def extract_tags_from_text(text: str) -> list[str]:
    '''Extract concept tags found in news text.'''
    matched_tags = []
    text_lower = text.lower()
    
    tag_keywords = {
        'AI': ['ai', '人工智能', '伺服器', 'nvidia', '輝達', '黃仁勳', '算力'],
        '半導體': ['半導體', '晶圓', '台積電', 'IC', '封測', '矽晶圓'],
        '記憶體': ['記憶體', 'dram', 'hbm', 'nand', '快閃記憶體', '南亞科', '華邦電', '群聯'],
        '散熱': ['散熱', '水冷', '液冷', '散熱模組', '奇鋐', '雙鴻'],
        '電源': ['電源', '台達電', '高功率'],
        'CoWoS': ['cowos', '先進封裝'],
        'ETF': ['etf', '高股息', '復華', '國泰', '元大'],
        '高股息': ['高股息', '股利', '殖利率', '配息']
    }

    for tag, kw_list in tag_keywords.items():
        if any(kw in text_lower for kw in kw_list):
            matched_tags.append(tag)

    return matched_tags or ['半導體', 'AI']


def get_companies_by_tags_filtered(tags: list[str], top_k: int = 3) -> list[str]:
    '''
    Query companies matching given tags, calculate Tag Weights, 
    and strictly return top_k candidates to avoid LLM bottleneck.
    '''
    candidate_scores: dict[str, float] = {}

    for tag in tags:
        companies = TAG_TO_COMPANIES.get(tag, [])
        for comp in companies:
            ticker = comp['ticker']
            weight = comp['weight']
            candidate_scores[ticker] = candidate_scores.get(ticker, 0.0) + weight

    # Sort candidates by cumulative tag weight score
    sorted_candidates = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
    top_tickers = [item[0] for item in sorted_candidates[:top_k]]
    
    logger.info(f"🏷️ [IndustryGraph] Tags {tags} -> Filtered Top {top_k} Candidates: {top_tickers}")
    return top_tickers or ['2330', '2454', '2382']
