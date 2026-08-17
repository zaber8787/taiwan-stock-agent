# File: agents/ml_predictor.py
"""
📈 機器學習 Alpha 機率預測器 (ML Alpha Predictor)
根據《台灣股市短線 AI 交易策略規劃書》，優先加載已訓練之 LightGBM / GBDT 模型權重檔案，
輸入 15+ 維量化因子，預測個股在 T+1 至 T+3 內實現至少 +5% 淨超額報酬的機率 P_alpha。
門檻要求：P_alpha >= 0.65 方可觸發高動能進場。
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pickle
import numpy as np

from crawlers.feature_engine import MicrostructureFeatures, extract_microstructure_features

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / 'ml' / 'models' / 'lgb_alpha_model.joblib'


@dataclass
class AlphaPrediction:
    """機器學習模型預測輸出"""
    ticker: str
    p_alpha: float                     # 實現 +5% 超額報酬機率 (0.0 ~ 1.0)
    is_high_conviction: bool           # 是否達到 P_alpha >= 0.65 門檻
    top_contributing_factors: list[str]# 前三大貢獻正向特徵
    risk_factors: list[str]            # 潛在扣分特徵
    predicted_return_pct: float        # 預估期望報酬率 (%)
    recommendation: str                # STRONG_BUY / BUY / NEUTRAL / AVOID
    model_source: str = "RULE_MATRIX"  # "LIGHTGBM_PERSISTED" or "RULE_MATRIX"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'p_alpha': self.p_alpha,
            'is_high_conviction': self.is_high_conviction,
            'top_contributing_factors': self.top_contributing_factors,
            'risk_factors': self.risk_factors,
            'predicted_return_pct': self.predicted_return_pct,
            'recommendation': self.recommendation,
            'model_source': self.model_source
        }


class MLAlphaPredictor:
    """台股微觀結構 LightGBM/梯度決策 Alpha 預測器"""

    ALPHA_THRESHOLD = 0.65

    def __init__(self, model_file: Optional[Path] = None):
        self.model_path = model_file or MODEL_PATH
        self.loaded_bundle = None
        self._load_persisted_model()

    def _load_persisted_model(self):
        """嘗試加載持久化模型權重檔案"""
        try:
            if self.model_path.exists():
                with open(self.model_path, 'rb') as f:
                    self.loaded_bundle = pickle.load(f)
                logger.info(f"✅ 成功加載持久化 LightGBM/GBDT 模型權重: {self.model_path}")
        except Exception as e:
            logger.warning(f"⚠️ 加載持久化模型權重失敗，降級為啟發式矩陣推論: {e}")
            self.loaded_bundle = None

    def predict(
        self,
        ticker: str,
        features: Optional[MicrostructureFeatures] = None
    ) -> AlphaPrediction:
        """
        輸入微觀結構特徵，優先使用已訓練的 GBDT 模型進行推論；若無模型則使用啟發式規則矩陣。
        """
        clean_ticker = ticker.replace('.TW', '')
        feats = features or extract_microstructure_features(clean_ticker)

        pos_factors: list[str] = []
        neg_factors: list[str] = []

        # 1. 整理可解釋性因子貢獻
        if feats.buyer_seller_spread_3d < -30:
            pos_factors.append(f"買賣家數差極度集中 ({feats.buyer_seller_spread_3d})")
        if feats.top10_buy_ratio >= 0.50:
            pos_factors.append(f"前十大券商買超佔比達 {(feats.top10_buy_ratio*100):.0f}%")
        if feats.is_early_limit_up:
            pos_factors.append("早盤 09:30 前強勢鎖死漲停 (次日開高溢價機率 > 70%)")
        if feats.vol_surge_ratio >= 3.0:
            pos_factors.append(f"量價雙突破 (量爆 {feats.vol_surge_ratio:.1f}x)")
        if feats.ma_alignment_score >= 90:
            pos_factors.append("均線標準多頭排列 (5MA>10MA>20MA)")

        if feats.next_day_broker_ratio > 0.10:
            neg_factors.append(f"隔日沖券商買超佔比過高 ({(feats.next_day_broker_ratio*100):.0f}%)")
        if feats.margin_maintenance_ratio < 140.0:
            neg_factors.append(f"融資維持率瀕臨斷頭線 ({feats.margin_maintenance_ratio:.1f}%)")

        # 2. 如果存在持久化模型，使用真實模型推論
        if self.loaded_bundle and 'model' in self.loaded_bundle:
            model = self.loaded_bundle['model']
            # 轉換為 13 維特徵向量
            feature_vector = np.array([[
                float(feats.buyer_seller_spread_3d),
                float(feats.top10_buy_ratio),
                float(feats.next_day_broker_ratio),
                float(feats.broker_cost_bias_pct),
                float(feats.vol_surge_ratio),
                float(feats.atr_5d_pct),
                float(feats.ma_alignment_score),
                1.0 if feats.is_early_limit_up else 0.0,
                float(feats.margin_maintenance_ratio),
                float(feats.foreign_net_buy_shares) / 1000.0,
                float(feats.trust_net_buy_shares) / 1000.0,
                float(feats.paid_in_capital_billion),
                float(feats.market_credit_ratio)
            ]])
            probs = model.predict_proba(feature_vector)[0]
            p_alpha = round(float(probs[1]), 3)
            model_src = "LIGHTGBM_PERSISTED"
        else:
            # 啟發式規則矩陣回退推算
            score = 0.50
            if feats.buyer_seller_spread_3d < -30:
                score += 0.08
            if feats.top10_buy_ratio >= 0.50:
                score += 0.07
            if feats.next_day_broker_ratio > 0.10:
                score -= 0.06
            if feats.is_20d_high and feats.vol_surge_ratio >= 3.0:
                score += 0.10
            elif feats.vol_surge_ratio >= 2.0:
                score += 0.04
            if feats.is_early_limit_up:
                score += 0.12
            if feats.foreign_net_buy_shares > 1000 and feats.trust_net_buy_shares > 500:
                score += 0.06
            if feats.ma_alignment_score >= 90:
                score += 0.05
            if feats.margin_maintenance_ratio < 140.0:
                score -= 0.15

            p_alpha = round(float(np.clip(score, 0.05, 0.95)), 3)
            model_src = "RULE_MATRIX"

        is_high_conviction = p_alpha >= self.ALPHA_THRESHOLD
        expected_ret = round((p_alpha - 0.50) * 15.0 + 2.5, 2)

        if p_alpha >= 0.75:
            recommendation = "STRONG_BUY"
        elif p_alpha >= 0.65:
            recommendation = "BUY"
        elif p_alpha <= 0.40:
            recommendation = "AVOID"
        else:
            recommendation = "NEUTRAL"

        return AlphaPrediction(
            ticker=clean_ticker,
            p_alpha=p_alpha,
            is_high_conviction=is_high_conviction,
            top_contributing_factors=pos_factors[:3],
            risk_factors=neg_factors[:2],
            predicted_return_pct=expected_ret,
            recommendation=recommendation,
            model_source=model_src
        )


def predict_stock_alpha(ticker: str, features: Optional[MicrostructureFeatures] = None) -> AlphaPrediction:
    """全域便利呼叫函數"""
    predictor = MLAlphaPredictor()
    return predictor.predict(ticker, features)
