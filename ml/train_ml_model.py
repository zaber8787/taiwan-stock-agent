# File: ml/train_ml_model.py
"""
🏋️‍♂️ 輕量 GBDT / 決策森林離線模型訓練器 (Offline GBDT Classifier)
使用純 numpy 構建零依賴、高穩健性之梯度提升決策樹 (GBDT)，
評估特徵重要性並持久化保存模型權重。
"""
from __future__ import annotations
import logging
import os
import pickle
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from ml.dataset_builder import generate_synthetic_historical_dataset, FEATURE_NAMES

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / 'models'
MODEL_PATH = MODEL_DIR / 'lgb_alpha_model.joblib'


class DecisionStump:
    """單一維度決策節點 (Decision Stump)"""
    def __init__(self):
        self.feature_idx: int = 0
        self.threshold: float = 0.0
        self.val_left: float = 0.0
        self.val_right: float = 0.0

    def fit(self, X: np.ndarray, residuals: np.ndarray):
        n_samples, n_features = X.shape
        best_mse = float('inf')

        for feat_i in range(n_features):
            x_col = X[:, feat_i]
            # 抽樣 15 個百分位數作為候選分割點
            percentiles = np.percentile(x_col, np.linspace(10, 90, 15))
            for thresh in percentiles:
                mask_left = x_col <= thresh
                mask_right = ~mask_left

                if not np.any(mask_left) or not np.any(mask_right):
                    continue

                left_mean = float(np.mean(residuals[mask_left]))
                right_mean = float(np.mean(residuals[mask_right]))

                mse = np.sum((residuals[mask_left] - left_mean) ** 2) + np.sum((residuals[mask_right] - right_mean) ** 2)

                if mse < best_mse:
                    best_mse = mse
                    self.feature_idx = feat_i
                    self.threshold = float(thresh)
                    self.val_left = left_mean
                    self.val_right = right_mean

    def predict(self, X: np.ndarray) -> np.ndarray:
        x_col = X[:, self.feature_idx]
        preds = np.where(x_col <= self.threshold, self.val_left, self.val_right)
        return preds


class NumpyGBDTClassifier:
    """基於 Numpy 的高效梯度提升二元分類器"""

    def __init__(self, n_estimators: int = 40, learning_rate: float = 0.15):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.trees: List[DecisionStump] = []
        self.base_pred: float = 0.0
        self.feature_importances_: np.ndarray = np.array([])

    def fit(self, X: np.ndarray, y: np.ndarray):
        n_samples, n_features = X.shape
        # 初始化先驗預測值
        pos_ratio = float(np.mean(y))
        pos_ratio = max(0.01, min(0.99, pos_ratio))
        self.base_pred = float(np.log(pos_ratio / (1.0 - pos_ratio)))

        raw_preds = np.full(n_samples, self.base_pred, dtype=float)
        feat_counts = np.zeros(n_features, dtype=float)

        self.trees = []
        for _ in range(self.n_estimators):
            # 計算機率與殘差
            probs = 1.0 / (1.0 + np.exp(-raw_preds))
            residuals = y - probs

            tree = DecisionStump()
            tree.fit(X, residuals)
            self.trees.append(tree)

            feat_counts[tree.feature_idx] += 1.0
            update = tree.predict(X)
            raw_preds += self.learning_rate * update

        total_splits = np.sum(feat_counts)
        self.feature_importances_ = feat_counts / total_splits if total_splits > 0 else np.ones(n_features) / n_features

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        n_samples = X.shape[0]
        raw_preds = np.full(n_samples, self.base_pred, dtype=float)

        for tree in self.trees:
            raw_preds += self.learning_rate * tree.predict(X)

        prob_pos = 1.0 / (1.0 + np.exp(-raw_preds))
        prob_neg = 1.0 - prob_pos
        return np.column_stack([prob_neg, prob_pos])

    def predict(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.50).astype(int)


def train_and_save_model(
    num_samples: int = 1500,
    save_path: Optional[Path] = None
) -> dict:
    """
    執行模型訓練並保存權重檔案。
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = save_path or MODEL_PATH

    print(f"🚀 開始構建台股微觀特徵歷史訓練數據集 ({num_samples} 筆樣本)...")
    X, y, feature_names = generate_synthetic_historical_dataset(num_samples=num_samples)

    split_idx = int(num_samples * 0.80)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"🌲 訓練 GBDT / LightGBM 梯度提升樹分類器 (Numpy Native)...")
    model = NumpyGBDTClassifier(n_estimators=35, learning_rate=0.18)
    model.fit(X_train, y_train)

    # 評估測試集表現
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    acc = float(np.mean(y_pred == y_test))

    print(f"📊 模型評估指標:")
    print(f"  準確率 (Accuracy): {acc:.2%}")

    # 特徵重要性排序
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    
    print("\n🔍 核心特徵重要性 (Top Feature Importance):")
    top_features = []
    for i in range(min(5, len(feature_names))):
        idx = sorted_idx[i]
        fname = feature_names[idx]
        imp = importances[idx]
        print(f"  {i+1}. {fname}: {imp:.4f} ({(imp*100):.1f}%)")
        top_features.append((fname, float(imp)))

    # 保存模型物件與特徵元數據
    bundle = {
        'model': model,
        'feature_names': feature_names,
        'accuracy': acc,
        'top_features': top_features
    }

    with open(out_path, 'wb') as f:
        pickle.dump(bundle, f)
    print(f"\n💾 模型權重已成功持久化保存至: {out_path}")

    return bundle


if __name__ == '__main__':
    train_and_save_model()
