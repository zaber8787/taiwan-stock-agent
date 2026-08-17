# File: crawlers/event_classifier.py
"""
🏷️ 金融即時新聞事件分類器 (Event Classifier)
將財經新聞、公開資訊觀測站公告與社群輿情自動精準歸類為：
1. 📊 EARNINGS: 財報 / 月營收 / EPS / 毛利率 / 法說會財測
2. 🤝 MA_EXPANSION: 併購 / 合資 / 海外擴建新廠 / 資本支出
3. ⚖️ REGULATORY_LEGAL: 監管 / 法規 / 訴訟 / 出口管制 / 處置注意股
4. 🏭 SUPPLY_CHAIN: 供應鏈 / 大客戶砍單追單 / 缺料 / 晶圓代工報價
5. 👥 MANAGEMENT_INSIDER: 董監申讓 / 庫藏股買回 / 經營權爭奪 / 高管異動
6. 🌐 MACRO_MARKET: 總體經濟 / 央行升降息 / 產業政策補助
7. 💬 SENTIMENT_RUMOR: 市場傳聞 / PTT熱議 / 概念股炒作
8. 📰 GENERAL: 一般產經綜述
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventCategory(str, Enum):
    """金融事件類型枚舉"""
    EARNINGS = "EARNINGS"                     # 財報營收
    MA_EXPANSION = "MA_EXPANSION"             # 併購擴產
    REGULATORY_LEGAL = "REGULATORY_LEGAL"     # 監管法規與訴訟
    SUPPLY_CHAIN = "SUPPLY_CHAIN"             # 供應鏈與訂單
    MANAGEMENT_INSIDER = "MANAGEMENT_INSIDER" # 董監內部人與庫藏股
    MACRO_MARKET = "MACRO_MARKET"             # 總經政策
    SENTIMENT_RUMOR = "SENTIMENT_RUMOR"       # 市場傳聞與輿情
    GENERAL = "GENERAL"                       # 一般產經


class EventUrgency(str, Enum):
    """事件緊急度"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImpactHorizon(str, Enum):
    """影響時間維度"""
    INTRADAY = "INTRADAY"       # 當日當沖 (1~2 小時)
    SHORT_TERM = "SHORT_TERM"   # 短線波段 (1~3 天)
    LONG_TERM = "LONG_TERM"     # 中長線結構 (數週~數月)


@dataclass
class ClassifiedEvent:
    """事件分類結果"""
    category: EventCategory
    category_name_zh: str
    urgency: EventUrgency
    impact_horizon: ImpactHorizon
    keywords_matched: List[str] = field(default_factory=list)
    sentiment_hint: str = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL
    summary_tag: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'category_name_zh': self.category_name_zh,
            'urgency': self.urgency.value,
            'impact_horizon': self.impact_horizon.value,
            'keywords_matched': self.keywords_matched,
            'sentiment_hint': self.sentiment_hint,
            'summary_tag': self.summary_tag
        }


# ============================================================================
# 台股特徵關鍵字庫與權重定義
# ============================================================================

_CATEGORY_METADATA = {
    EventCategory.EARNINGS: {
        'name_zh': '📊 財報營收',
        'default_horizon': ImpactHorizon.SHORT_TERM,
        'keywords': [
            '營收', '財報', 'eps', '毛利率', '營業利益', '獲利', '淨利', '法說會', '展望',
            '財測', '每股盈餘', '季報', '年報', '虧損', '轉虧為盈', '創歷史新高', '創單月新高',
            '年增', '月增', 'yoy', 'mom', '填息', '除息', '股利', '配息', '現金股利'
        ]
    },
    EventCategory.MA_EXPANSION: {
        'name_zh': '🤝 併購擴廠',
        'default_horizon': ImpactHorizon.LONG_TERM,
        'keywords': [
            '併購', '收購', '入股', '合資', '建廠', '擴廠', '擴產', '資本支出', 'capex',
            '新廠', '量產', '投資案', '策略聯盟', '換股', '增資', '私募', '發債', '可轉債'
        ]
    },
    EventCategory.REGULATORY_LEGAL: {
        'name_zh': '⚖️ 監管法規',
        'default_horizon': ImpactHorizon.SHORT_TERM,
        'keywords': [
            '制裁', '禁令', '出口管制', '反壟斷', '訴訟', '專利戰', '侵權', '罰款', '處罰',
            '注意股', '處置股', '列入注意', '停牌', '暫停交易', '金管會', '證交所', '調查',
            '違約交割', '掏空', '假扣押', '地緣政治', '國安審查', '關稅'
        ]
    },
    EventCategory.SUPPLY_CHAIN: {
        'name_zh': '🏭 供應鏈訂單',
        'default_horizon': ImpactHorizon.SHORT_TERM,
        'keywords': [
            '訂單', '供應鏈', '砍單', '追單', '缺料', '滿載', '代工報價', '調漲', '降價',
            '蘋果', '輝達', 'nvidia', 'apple', '超微', 'amd', '特斯拉', '拉貨', '出貨',
            '缺貨', '封裝', 'cowos', '先進封裝', '客戶認證', '交期'
        ]
    },
    EventCategory.MANAGEMENT_INSIDER: {
        'name_zh': '👥 董監內部人',
        'default_horizon': ImpactHorizon.SHORT_TERM,
        'keywords': [
            '申報轉讓', '董監持股', '大股東', '庫藏股', '買回庫藏股', '經營權', '董事長',
            '總經理', '高管異動', '辭職', '接任', '減資', '股東會', '董事會'
        ]
    },
    EventCategory.MACRO_MARKET: {
        'name_zh': '🌐 總體政策',
        'default_horizon': ImpactHorizon.SHORT_TERM,
        'keywords': [
            '央行', '降息', '升息', '通膨', 'cpi', '聯準會', 'fed', '國安基金', '補助',
            '政策', '晶片法案', '景氣對策信號', '匯率', '台幣貶值', '台幣升值', '非農'
        ]
    },
    EventCategory.SENTIMENT_RUMOR: {
        'name_zh': '💬 社群傳聞',
        'default_horizon': ImpactHorizon.INTRADAY,
        'keywords': [
            '傳出', '傳言', '市場傳', '小道消息', 'ptt', '熱議', '爆料', '炒作', '概念股',
            '網友', '主力', '投顧', '軋空', '大戶'
        ]
    }
}

_BULLISH_KEYWORDS = {
    '創高', '大增', '激增', '突破', '優於預期', '超預期', '利多', '翻紅', '強勁', '買進',
    '上修', '爆單', '搶單', '漲價', '轉虧為盈', '庫藏股', '加碼', '奪單', '擴產'
}

_BEARISH_KEYWORDS = {
    '衰退', '大跌', '重挫', '暴跌', '不如預期', '利空', '翻黑', '砍單', '下修', '調降',
    '虧損', '訴訟', '制裁', '禁令', '罰款', '處置', '注意股', '申報轉讓', '跳水'
}


def classify_news_event(title: str, summary: str = "") -> ClassifiedEvent:
    """
    對財經新聞標題與內容進行多維度事件分類。
    
    返回 ClassifiedEvent，包含：
    - category: 事件類別 (EARNINGS, MA_EXPANSION, etc.)
    - category_name_zh: 中文類別標籤與圖標
    - urgency: 緊急程度 (LOW ~ CRITICAL)
    - impact_horizon: 影響週期 (INTRADAY / SHORT_TERM / LONG_TERM)
    - keywords_matched: 命中的特徵詞
    - sentiment_hint: 初步多空傾向 (BULLISH / BEARISH / NEUTRAL)
    """
    full_text = f"{title} {summary}".lower()
    
    scores: Dict[EventCategory, int] = {cat: 0 for cat in EventCategory if cat != EventCategory.GENERAL}
    matched_by_cat: Dict[EventCategory, List[str]] = {cat: [] for cat in EventCategory if cat != EventCategory.GENERAL}
    
    # 計算各類別權重
    for cat, meta in _CATEGORY_METADATA.items():
        for kw in meta['keywords']:
            # 標題命中權重 * 3，內文命中權重 * 1
            title_hits = title.lower().count(kw)
            summary_hits = summary.lower().count(kw)
            if title_hits > 0 or summary_hits > 0:
                score = (title_hits * 3) + summary_hits
                scores[cat] += score
                matched_by_cat[cat].append(kw)

    # 找出最高分類別
    best_cat = EventCategory.GENERAL
    max_score = 0
    for cat, score in scores.items():
        if score > max_score:
            max_score = score
            best_cat = cat

    # 若最高分小於等於 1 且無顯著特徵，歸為 GENERAL
    if max_score <= 1:
        best_cat = EventCategory.GENERAL

    matched_keywords = matched_by_cat.get(best_cat, [])

    # 判斷多空情緒傾向
    bull_count = sum(1 for kw in _BULLISH_KEYWORDS if kw in full_text)
    bear_count = sum(1 for kw in _BEARISH_KEYWORDS if kw in full_text)
    if bull_count > bear_count:
        sentiment = "BULLISH"
    elif bear_count > bull_count:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    # 決定緊急程度 (Urgency)
    urgency = EventUrgency.LOW
    if best_cat == EventCategory.REGULATORY_LEGAL:
        # 監管/制裁/處置股通常屬於高緊急度
        urgency = EventUrgency.CRITICAL if ('處置' in full_text or '制裁' in full_text or '停牌' in full_text) else EventUrgency.HIGH
    elif best_cat == EventCategory.EARNINGS:
        urgency = EventUrgency.HIGH if ('法說會' in full_text or '新高' in full_text or '超預期' in full_text) else EventUrgency.MEDIUM
    elif best_cat in (EventCategory.MA_EXPANSION, EventCategory.SUPPLY_CHAIN):
        urgency = EventUrgency.HIGH if ('併購' in full_text or '砍單' in full_text or '爆單' in full_text) else EventUrgency.MEDIUM
    elif best_cat == EventCategory.MANAGEMENT_INSIDER:
        urgency = EventUrgency.HIGH if ('申報轉讓' in full_text or '庫藏股' in full_text) else EventUrgency.MEDIUM
    else:
        urgency = EventUrgency.LOW if best_cat == EventCategory.GENERAL else EventUrgency.MEDIUM

    # 決定影響週期
    if best_cat in _CATEGORY_METADATA:
        horizon = _CATEGORY_METADATA[best_cat]['default_horizon']
        name_zh = _CATEGORY_METADATA[best_cat]['name_zh']
    else:
        horizon = ImpactHorizon.SHORT_TERM
        name_zh = "📰 一般產經"

    summary_tag = f"[{name_zh}] {title[:40]}"

    return ClassifiedEvent(
        category=best_cat,
        category_name_zh=name_zh,
        urgency=urgency,
        impact_horizon=horizon,
        keywords_matched=matched_keywords[:6],
        sentiment_hint=sentiment,
        summary_tag=summary_tag
    )
