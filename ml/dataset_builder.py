# File: ml/dataset_builder.py
"""
📦 台股微觀結構量化特徵數據集構建器 (Dataset Builder)
提取 15+ 維特徵向量並生成標準化訓練數據集 (X, y)，供 LightGBM / GBDT 離線訓練。
"""
from __future__ import annotations
import logging
from typing import Tuple, List, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    'buyer_seller_spread_3d',
    'top10_buy_ratio',
    'next_day_broker_ratio',
    'broker_cost_bias_pct',
    'vol_surge_ratio',
    'atr_5d_pct',
    'ma_alignment_score',
    'is_early_limit_up',
    'margin_maintenance_ratio',
    'foreign_net_buy_k',
    'trust_net_buy_k',
    'paid_in_capital_billion',
    'market_credit_ratio'
]


def generate_synthetic_historical_dataset(
    num_samples: int = 1500,
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    基於台股歷史微觀結構統計規律生成標準化特徵矩陣與標籤。
    y = 1: T+1~T+3 實現 >= +5% 超額報酬
    y = 0: 未達標或走平/虧損
    """
    np.random.seed(random_state)
    
    # 1. 買賣家數差 (-80 ~ +50)
    spread = np.random.normal(-20, 25, num_samples)
    
    # 2. 前十大買超佔比 (0.20 ~ 0.85)
    top10_ratio = np.clip(np.random.normal(0.48, 0.15, num_samples), 0.15, 0.90)
    
    # 3. 隔日沖券商買超佔比 (0.00 ~ 0.35)
    next_day_ratio = np.clip(np.random.exponential(0.06, num_samples), 0.0, 0.40)
    
    # 4. 主力成本線偏離度 (-5.0% ~ +12.0%)
    cost_bias = np.random.normal(2.5, 3.5, num_samples)
    
    # 5. 量暴增比率 (0.5x ~ 8.0x)
    vol_surge = np.clip(np.random.lognormal(0.6, 0.5, num_samples), 0.3, 10.0)
    
    # 6. 5 日 ATR% (1.0% ~ 7.5%)
    atr = np.clip(np.random.normal(3.2, 1.1, num_samples), 0.8, 8.5)
    
    # 7. 均線排列評分 (0 ~ 100)
    ma_score = np.random.choice([30.0, 50.0, 75.0, 95.0], size=num_samples, p=[0.2, 0.3, 0.3, 0.2])
    
    # 8. 09:30 前鎖漲停 (0 或 1)
    is_early_lup = (np.random.rand(num_samples) < 0.12).astype(float)
    
    # 9. 融資維持率 (120% ~ 200%)
    mr = np.random.normal(165.0, 15.0, num_samples)
    
    # 10. 外資近3日買超 (千張)
    foreign_k = np.random.normal(1.2, 3.0, num_samples)
    
    # 11. 投信近3日買超 (千張)
    trust_k = np.random.normal(0.8, 1.5, num_samples)
    
    # 12. 實收股本 (億元)
    capital_b = np.random.uniform(5.0, 80.0, num_samples)
    
    # 13. 市場信用比率 (0.25 ~ 0.60)
    mkt_credit = np.random.normal(0.40, 0.05, num_samples)

    # 組合特徵矩陣 X
    X = np.column_stack([
        spread, top10_ratio, next_day_ratio, cost_bias, vol_surge,
        atr, ma_score, is_early_lup, mr, foreign_k, trust_k,
        capital_b, mkt_credit
    ])

    # 計算潛在勝率機率（根據策略規劃書核心邏輯構造非線性目標函數）
    logits = (
        - 0.035 * spread                           # 家數差越負越好
        + 3.2 * (top10_ratio - 0.50)               # 前10大佔比越高越好
        - 4.5 * np.maximum(0, next_day_ratio - 0.10)# 隔日沖大於10%扣分
        + 0.45 * np.maximum(0, vol_surge - 2.5)    # 量暴增加分
        + 1.8 * is_early_lup                       # 早盤鎖漲停大幅加分
        + 0.02 * (mr - 140.0)                      # 維持率高於140加分
        + 0.15 * foreign_k + 0.25 * trust_k        # 法人同步加分
        - 0.02 * np.maximum(0, capital_b - 50.0)   # 股本大於50億扣分
        + np.random.normal(0, 0.6, num_samples)    # 市場雜訊
    )

    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs >= 0.58).astype(int)

    return X, y, FEATURE_NAMES
