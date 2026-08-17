# File: crawlers/market_regime.py
"""
🌐 台股市場狀態偵測器 (Market Regime Detector)
精準辨識：
1. 🐂 BULL (多頭市場): 指數 > 20MA > 60MA，均線多頭排列，動量順勢做多 (100% 撥款，-6% 停損)
2. 🐻 BEAR (空頭市場): 指數 < 20MA < 60MA，均線空頭排列，防禦避險 (0~30% 撥款，-3% 停損，拒絕弱勢追高)
3. 🦀 RANGING (盤整市場): 指數在 20MA 上下糾結，均線收窄，區間短打 (50~60% 撥款，-4% 停損，T+2 快速出場)
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """市場狀態枚舉"""
    BULL = "BULL"          # 🐂 多頭趨勢
    BEAR = "BEAR"          # 🐻 空頭修正
    RANGING = "RANGING"    # 🦀 箱型盤整


class StrategyMode(str, Enum):
    """建議策略模式"""
    MOMENTUM_TREND = "MOMENTUM_TREND"   # 順勢動量策略
    DEFENSIVE_CASH = "DEFENSIVE_CASH"   # 防禦現金為王
    MEAN_REVERSION = "MEAN_REVERSION"   # 區間均值回歸


@dataclass
class MarketState:
    """市場狀態評估結果"""
    regime: MarketRegime
    regime_name_zh: str
    confidence: float
    strategy_mode: StrategyMode
    allocation_multiplier: float        # 資金撥款乘數 (1.0 / 0.6 / 0.3)
    suggested_stop_loss_pct: float      # 建議停損百分比 (-6.0 / -4.0 / -3.0)
    suggested_take_profit_pct: float    # 建議停利百分比 (+10.0 / +6.0 / +4.0)
    suggested_max_holding_days: int     # 建議最大持有日 (4 / 2 / 1)
    taiex_price: float                  # 加權指數現價
    ma20: float                         # 20MA 月線
    ma60: float                         # 60MA 季線
    bias_ma20_pct: float                # 與 20MA 乖離率 (%)
    indicators: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'regime': self.regime.value,
            'regime_name_zh': self.regime_name_zh,
            'confidence': self.confidence,
            'strategy_mode': self.strategy_mode.value,
            'allocation_multiplier': self.allocation_multiplier,
            'suggested_stop_loss_pct': self.suggested_stop_loss_pct,
            'suggested_take_profit_pct': self.suggested_take_profit_pct,
            'suggested_max_holding_days': self.suggested_max_holding_days,
            'taiex_price': self.taiex_price,
            'ma20': self.ma20,
            'ma60': self.ma60,
            'bias_ma20_pct': self.bias_ma20_pct,
            'indicators': self.indicators,
            'rationale': self.rationale
        }


def detect_market_regime(
    price_series: Optional[List[float]] = None,
    current_price: Optional[float] = None
) -> MarketState:
    """
    偵測當前台股市場狀態 (Market Regime)。
    若未傳入價格序列，自動嘗試從 TWSE 或 yfinance 抓取加權指數歷史數據，
    若抓取異常則採用基準均線推算模型。
    """
    # 嘗試從 yfinance 獲取加權指數 ^TWII 或 0050.TW 代替
    if not price_series or len(price_series) < 20:
        prices = _fetch_taiex_prices()
    else:
        prices = price_series

    if not prices or len(prices) < 20:
        raise ValueError("❌ [大盤狀態評估失敗] 無法從 TWSE / yfinance 獲取真實加權指數行情數據，拒絕使用虛假預設值！")

    # 計算關鍵技術指標
    arr = np.array(prices, dtype=float)
    latest_close = current_price if current_price else float(arr[-1])
    
    ma5 = float(np.mean(arr[-5:])) if len(arr) >= 5 else latest_close
    ma20 = float(np.mean(arr[-20:])) if len(arr) >= 20 else latest_close
    ma60 = float(np.mean(arr[-60:])) if len(arr) >= 60 else latest_close
    
    bias_ma20 = ((latest_close - ma20) / ma20) * 100.0
    bias_ma60 = ((latest_close - ma60) / ma60) * 100.0

    # 計算 20 日布林帶寬度 (Bandwidth)
    std20 = float(np.std(arr[-20:])) if len(arr) >= 20 else 0.0
    bandwidth_pct = (2 * std20 / ma20) * 100.0 if ma20 > 0 else 0.0

    # 計算斜率 (Slope of 20MA over 5 days)
    if len(arr) >= 25:
        ma20_prev = float(np.mean(arr[-25:-5]))
        ma20_slope_pct = ((ma20 - ma20_prev) / ma20_prev) * 100.0
    else:
        ma20_slope_pct = 0.0

    # --- 狀態研判邏輯 (Decision Tree Matrix) ---
    bull_score = 0
    bear_score = 0

    # 1. 均線位置加分
    if latest_close > ma20:
        bull_score += 2
    else:
        bear_score += 2

    if latest_close > ma60:
        bull_score += 2
    else:
        bear_score += 2

    # 2. 均線排列加分
    if ma5 > ma20 > ma60:
        bull_score += 3
    elif ma5 < ma20 < ma60:
        bear_score += 3

    # 3. 20MA 趨勢斜率
    if ma20_slope_pct > 0.5:
        bull_score += 2
    elif ma20_slope_pct < -0.5:
        bear_score += 2

    # 4. 判斷是否屬於「盤整市場」
    # 盤整特徵：
    # - 價格在 20MA 附近 (乖離率極低 abs(bias_ma20) <= 1.0%)
    # - 布林帶寬度極窄 (< 2.5%) 或均線高度糾結
    # - 20MA 斜率平坦 (abs(ma20_slope_pct) < 0.4%)
    is_tight_bandwidth = bandwidth_pct < 2.0
    is_flat_slope = abs(ma20_slope_pct) < 0.4
    is_ranging_bias = abs(bias_ma20) <= 1.0
    is_ranging_ma = abs(ma5 - ma20) / ma20 <= 0.005
    score_diff = abs(bull_score - bear_score)

    if (is_tight_bandwidth or (is_ranging_bias and is_flat_slope) or is_ranging_ma) and score_diff <= 7:
        regime = MarketRegime.RANGING
        regime_name = "🦀 箱型盤整"
        confidence = 0.70
        strategy = StrategyMode.MEAN_REVERSION
        allocation_mult = 0.60
        stop_loss = -4.0
        take_profit = 6.0
        max_days = 2
        rationale = (
            f"加權指數 (${latest_close:,.0f}) 在月線 20MA (${ma20:,.0f}) 附近狹幅震盪 (乖離 {bias_ma20:+.2f}%)，"
            f"均線糾結且帶寬收窄 ({bandwidth_pct:.1f}%)，建議採取箱型區間操作，撥款限縮為 60%，收緊停損至 -4%，縮短持有至 T+2。"
        )
    elif bull_score > bear_score:
        regime = MarketRegime.BULL
        regime_name = "🐂 多頭趨勢"
        confidence = min(0.95, 0.60 + (bull_score * 0.04))
        strategy = StrategyMode.MOMENTUM_TREND
        allocation_mult = 1.00
        stop_loss = -6.0
        take_profit = 10.0
        max_days = 4
        rationale = (
            f"加權指數 (${latest_close:,.0f}) 站穩 20MA (${ma20:,.0f}) 與 60MA (${ma60:,.0f})，"
            f"均線呈多頭排列且動能強勁 (乖離 {bias_ma20:+.2f}%)，核准 100% 滿額撥款，執行標準順勢波段策略。"
        )
    else:
        regime = MarketRegime.BEAR
        regime_name = "🐻 空頭修正"
        confidence = min(0.95, 0.60 + (bear_score * 0.04))
        strategy = StrategyMode.DEFENSIVE_CASH
        allocation_mult = 0.30
        stop_loss = -3.0
        take_profit = 5.0
        max_days = 1
        rationale = (
            f"加權指數 (${latest_close:,.0f}) 跌破 20MA (${ma20:,.0f})，均線空頭反壓 (乖離 {bias_ma20:+.2f}%)，"
            f"市場處於空頭弱勢格局，啟動嚴格防禦機制：嚴禁追高，單筆撥款上限降至 30%，停損縮緊至 -3%。"
        )

    return MarketState(
        regime=regime,
        regime_name_zh=regime_name,
        confidence=round(confidence, 2),
        strategy_mode=strategy,
        allocation_multiplier=allocation_mult,
        suggested_stop_loss_pct=stop_loss,
        suggested_take_profit_pct=take_profit,
        suggested_max_holding_days=max_days,
        taiex_price=round(latest_close, 2),
        ma20=round(ma20, 2),
        ma60=round(ma60, 2),
        bias_ma20_pct=round(bias_ma20, 2),
        indicators={
            'ma5': round(ma5, 2),
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            'bandwidth_pct': round(bandwidth_pct, 2),
            'ma20_slope_pct': round(ma20_slope_pct, 2),
            'bull_score': bull_score,
            'bear_score': bear_score
        },
        rationale=rationale
    )


def _fetch_taiex_prices() -> List[float]:
    """從 yfinance 抓取台股加權指數 (^TWII) 或 0050.TW 近 3 個月日收盤價"""
    try:
        import yfinance as yf
        for symbol in ["^TWII", "0050.TW"]:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")
            if not hist.empty and len(hist) >= 20:
                return hist['Close'].tolist()
    except Exception as e:
        logger.debug(f"抓取大盤指數數據異常: {e}")
    return []
