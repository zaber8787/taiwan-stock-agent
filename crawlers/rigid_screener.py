# File: crawlers/rigid_screener.py
"""
🔍 剛性進場篩選濾網 (Rigid Entry Screener)
根據《台灣股市短線 AI 交易策略規劃書》，只有同時滿足以下交集條件的個股，
才允許進入 AI 與風控撮合流水線：
1. 【流動性與股本限制】: 20日均量 > 3,000 張 且 實收股本 < 50 億元（避免淺碟黑天鵝與笨重權值股）。
2. 【波動度門檻】: 5 日 ATR% >= 2.5%（確保獲利空間足以覆蓋 0.357% 摩擦成本）。
3. 【動能突破共振】: 收盤價創 20 日新高 且 當日成交量 >= 20日均量的 3 倍 (V/MA20 >= 3.0)。
4. 【主力籌碼鎖碼】: 買賣家數差連續 3 天 < -30 且 前十大買超比率 > 50%。
5. 【信用安全底線】: 個股融資維持率 MR >= 140%（排除追繳斷頭連環殺）。
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from crawlers.feature_engine import MicrostructureFeatures, extract_microstructure_features

logger = logging.getLogger(__name__)


@dataclass
class ScreenerResult:
    """剛性篩選器檢驗結果"""
    ticker: str
    passed: bool
    rejection_reasons: List[str] = field(default_factory=list)
    passed_filters: List[str] = field(default_factory=list)
    features: Optional[MicrostructureFeatures] = None
    is_early_limit_up: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'passed': self.passed,
            'rejection_reasons': self.rejection_reasons,
            'passed_filters': self.passed_filters,
            'is_early_limit_up': self.is_early_limit_up,
            'features': self.features.to_dict() if self.features else {}
        }


def check_rigid_entry_filters(
    ticker: str,
    features: Optional[MicrostructureFeatures] = None
) -> ScreenerResult:
    """
    執行剛性進場篩選檢驗。
    若未傳入特徵物件，自動提取。
    """
    clean_ticker = ticker.replace('.TW', '')
    feats = features or extract_microstructure_features(clean_ticker)

    rejections: List[str] = []
    passes: List[str] = []

    # 1. 流動性與股本限制
    if feats.volume_20ma < 3000.0:
        rejections.append(f"20日均量不足 ({feats.volume_20ma:,.0f} 張 < 3,000 張)")
    elif feats.paid_in_capital_billion >= 50.0:
        rejections.append(f"實收股本過大 ({feats.paid_in_capital_billion:.1f} 億 >= 50 億)")
    else:
        passes.append("流動性與股本合格 (20日均量>3000張 & 股本<50億)")

    # 2. 波動度門檻 (ATR% >= 2.5%)
    if feats.atr_5d_pct < 2.5:
        rejections.append(f"5日波動度過低 (ATR% {feats.atr_5d_pct:.2f}% < 2.5%，獲利難以覆蓋交易摩擦)")
    else:
        passes.append(f"波動度合格 (5日 ATR% {feats.atr_5d_pct:.2f}% >= 2.5%)")

    # 3. 動能突破與量能共振 (創20日新高 且 量增 >= 3倍)
    if not feats.is_20d_high:
        rejections.append("收盤價未創 20 日新高")
    elif feats.vol_surge_ratio < 3.0:
        rejections.append(f"成交量未達暴增 3 倍 (當前量能比 {feats.vol_surge_ratio:.2f}x < 3.0x)")
    else:
        passes.append(f"動能突破共振 (創20日新高 且 量暴增 {feats.vol_surge_ratio:.2f}x)")

    # 4. 主力籌碼鎖碼驗證 (家數差 < -30 & 前10大買超 > 50%)
    if feats.buyer_seller_spread_3d >= -30:
        rejections.append(f"買賣家數差未達鎖碼標準 ({feats.buyer_seller_spread_3d} >= -30)")
    elif feats.top10_buy_ratio < 0.50:
        rejections.append(f"前十大券商買超佔比不足 ({(feats.top10_buy_ratio*100):.1f}% < 50%)")
    else:
        passes.append(f"主力籌碼高度鎖碼 (家數差 {feats.buyer_seller_spread_3d} & 前10買超 {(feats.top10_buy_ratio*100):.1f}%)")

    # 5. 信用安全過濾 (融資維持率 >= 140%)
    if feats.margin_maintenance_ratio < 140.0:
        rejections.append(f"融資維持率過低 ({feats.margin_maintenance_ratio:.1f}% < 140%，具追繳斷頭風險)")
    else:
        passes.append(f"信用交易安全 (融資維持率 {feats.margin_maintenance_ratio:.1f}% >= 140%)")

    passed_all = len(rejections) == 0

    return ScreenerResult(
        ticker=clean_ticker,
        passed=passed_all,
        rejection_reasons=rejections,
        passed_filters=passes,
        features=feats,
        is_early_limit_up=feats.is_early_limit_up
    )
