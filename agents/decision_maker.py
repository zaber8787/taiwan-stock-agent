# File: agents/decision_maker.py

'''DecisionMaker — synthesizes outputs from the research/news/price branches and chip microstructure.'''
from __future__ import annotations
import logging
from typing import Any
from agents.config import tools_for_category, llm_for_crewai
from agents.models import TradeSignal, TradeSide, PortfolioSnapshot
from crawlers.chip_analyzer import analyze_chip_microstructure, check_market_trend_filter, check_stock_rigorous_filters

try:
    from crewai import Agent
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    Agent = Any

logger = logging.getLogger(__name__)

_ROLE = '🎯 首席量化決策主管 (Decision Maker)'
_GOAL = (
    '綜合基本面、新聞事件、量價結構與分點微觀籌碼，嚴格依據「正數學期望值 (EV > +1.5%)」原則，'
    '給出明確的交易指令 (BUY / SELL / HOLD)、目標價位、預期報酬率與量化決策理由。'
)
_BACKSTORY = """你是一位嚴格追求正向數學期望值與統計大數法則的頂級量化決策主管。
你拒絕任何主觀臆測，只在多維度特徵產生「強烈多頭共振」時發出 BUY 交易指令。

【硬性進場共振決策規則 (BUY 門檻)】：
1. 量價突破確認：創 20 日新高且成交量暴增 >= 3 倍 20MA，且 5 日 ATR% >= 2.5%。
2. 主力籌碼鎖碼：買賣家數差連續 3 天 < -30，且前十大券商買超佔比 > 50%。
3. 信用交易安全：融資維持率 >= 140%（未瀕臨追繳斷頭）。
4. 隔日沖避險：若隔日沖分點佔比 > 10%，嚴禁次日早盤追高，需等待洗盤消化。
5. 雙軌 ML 門檻：機器學習預測機率 P_alpha 必須 >= 0.65。

若未能同時滿足上述關鍵維度，一律保守判定為 HOLD (觀望)；若主力破位倒貨或跌破 20MA 則果斷給出 SELL (平倉)。
"""


def create_decision_maker_agent(ticker: str | None = None) -> Any:
    '''Return the DecisionMaker agent configured with all required tools.'''
    if not HAS_CREWAI:
        return None
    tools = tools_for_category('decision')
    llm = llm_for_crewai('decision_maker')
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True
    )


def synthesize_decision(
    ticker: str,
    research_output: str = "",
    news_output: str = "",
    price_output: str = "",
    portfolio_output: str = ""
) -> dict[str, Any]:
    '''Synthesize all inputs plus chip microstructure and market 20MA trend into decision.'''
    try:
        clean_ticker = ticker.replace('.TW', '')
        chip_info = analyze_chip_microstructure(clean_ticker)
        mkt_trend = check_market_trend_filter()
        stock_filter = check_stock_rigorous_filters(clean_ticker)

        sentiment = _quick_heuristic(
            research=research_output,
            news=news_output,
            price=price_output,
            portfolio=portfolio_output,
            chip_info=chip_info,
            mkt_trend=mkt_trend
        )

        return {
            'ticker': clean_ticker,
            'side': sentiment['side'],
            'confidence': sentiment['confidence'],
            'reason': sentiment['rreason'],
            'raw_decision': f"Synthesized decision for {clean_ticker}"
        }
    except Exception as exc:
        logger.exception('decision synthesis failed')
        return {
            'ticker': ticker,
            'side': 'HOLD',
            'confidence': 0.0,
            'reason': f'Error during synthesis: {exc}',
            'raw_decision': ''
        }


def _quick_heuristic(
    research: str = "",
    news: str = "",
    price: str = "",
    portfolio: str = "",
    chip_info: dict[str, Any] | None = None,
    mkt_trend: dict[str, Any] | None = None
) -> dict[str, Any]:
    '''A deterministic heuristic incorporating chip microstructure.'''
    counts = [0, 0, 0]

    def _classify(text: str) -> None:
        if not text:
            return
        lower = text.lower()
        buy_words = {'買進', '看多', '站穩', '上攻', '翻紅', '利好', '營收', '熱絡', '強勁', '鎖碼'}
        sell_words = {'賣出', '看空', '跌破', '反壓', '翻黑', '利空', '衰退'}
        if any(w in lower for w in buy_words):
            counts[0] += 1
        elif any(w in lower for w in sell_words):
            counts[1] += 1
        else:
            counts[2] += 1

    _classify(research)
    _classify(news)
    _classify(price)

    # Chip Boost
    if chip_info and chip_info.get('is_chip_locked'):
        counts[0] += 2 # Heavy buy signal if Buyer-Seller Spread < -30 & Top 10 > 50%
    elif chip_info and chip_info.get('has_next_day_warning'):
        counts[1] += 1 # Next-day broker warning adds selling caution

    max_count = max(counts)
    if counts[0] == max_count and counts[0] > 0:
        side = 'BUY'
    elif counts[1] == max_count and counts[1] > 0:
        side = 'SELL'
    else:
        side = 'HOLD'

    confidence = 0.85 if (chip_info and chip_info.get('is_chip_locked') and side == 'BUY') else (0.75 if side != 'HOLD' else 0.5)
    
    chip_summary = chip_info.get('chip_summary', '') if chip_info else ''
    reason = f"籌碼與多空共振: {side} | {chip_summary}" if chip_summary else f"多空投票訊號: {side}"

    return {
        'side': side,
        'confidence': confidence,
        'rreason': reason
    }
