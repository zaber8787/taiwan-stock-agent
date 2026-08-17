#!/usr/bin/env python3
"""
🤖 機器學習離線訓練與持久化推論管線測試腳本
"""
import os
import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from ml.train_ml_model import train_and_save_model, MODEL_PATH
from agents.ml_predictor import MLAlphaPredictor, predict_stock_alpha
from crawlers.feature_engine import extract_microstructure_features


def test_ml_pipeline():
    print("=" * 70)
    print("🤖 測試台股微觀結構 LightGBM / GBDT 模型離線訓練與持久化推論")
    print("=" * 70)

    # 1. 訓練並導出模型權重
    bundle = train_and_save_model(num_samples=2500)
    assert MODEL_PATH.exists(), f"Model file must exist at {MODEL_PATH}"
    print(f"\n[1] 模型檔案驗證成功: {MODEL_PATH} (大小: {MODEL_PATH.stat().st_size / 1024:.1f} KB)")

    # 2. 測試 MLAlphaPredictor 自動加載持久化權重進行推論
    predictor = MLAlphaPredictor()
    assert predictor.loaded_bundle is not None, "Predictor must successfully load the persisted model!"

    # 測試多頭強勢股
    bull_feats = extract_microstructure_features("2330", lock_time_str="09:15")
    pred_bull = predictor.predict("2330", bull_feats)
    print(f"\n[2] 測試標的 (強勢多頭 2330):")
    print(f"  推論來源 (Source): {pred_bull.model_source}")
    print(f"  P_alpha 預測機率: {pred_bull.p_alpha:.1%}")
    print(f"  預估期望報酬率: {pred_bull.predicted_return_pct:+.2f}%")
    print(f"  建議評級: {pred_bull.recommendation}")
    print(f"  核心正向特徵: {', '.join(pred_bull.top_contributing_factors)}")

    assert pred_bull.model_source == "LIGHTGBM_PERSISTED"
    assert pred_bull.p_alpha >= 0.50

    print("\n" + "=" * 70)
    print("✅ LightGBM / GBDT 離線訓練與持久化推論測試 100% 通過！")
    print("=" * 70)


if __name__ == '__main__':
    test_ml_pipeline()
