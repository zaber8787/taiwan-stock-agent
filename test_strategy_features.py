#!/usr/bin/env python3
"""
⚡ 台股微觀策略特徵工程、剛性快篩與 ML 預測器測試腳本
"""
import os
import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent))

from crawlers.feature_engine import extract_microstructure_features
from crawlers.rigid_screener import check_rigid_entry_filters
from agents.ml_predictor import predict_stock_alpha


def test_microstructure_pipeline():
    print("=" * 70)
    print("⚡ 測試台股微觀結構特徵工程與剛性快篩器 (Microstructure Strategy)")
    print("=" * 70)

    # 1. 測試特徵提取
    feats = extract_microstructure_features("2330", lock_time_str="09:20")
    print(f"\n[1] 標的: {feats.ticker}")
    print(f"  買賣家數差(3日): {feats.buyer_seller_spread_3d} (<-30 表主力鎖碼)")
    print(f"  前十大買超佔比: {(feats.top10_buy_ratio*100):.1f}%")
    print(f"  隔日沖佔比: {(feats.next_day_broker_ratio*100):.1f}%")
    print(f"  量暴增比率: {feats.vol_surge_ratio:.2f}x")
    print(f"  5日 ATR%: {feats.atr_5d_pct:.2f}%")
    print(f"  融資維持率: {feats.margin_maintenance_ratio:.1f}%")
    print(f"  早盤鎖漲停: {feats.is_early_limit_up}")

    # 2. 測試剛性進場快篩濾網
    screen_res = check_rigid_entry_filters("2330", feats)
    print(f"\n[2] 剛性進場篩選結果: {'✅ 通過' if screen_res.passed else '⛔ 攔截'}")
    if screen_res.passed:
        print("  通過條件:")
        for p in screen_res.passed_filters:
            print(f"    - {p}")
    else:
        print("  攔截原因:")
        for r in screen_res.rejection_reasons:
            print(f"    - {r}")

    # 3. 測試 ML Alpha 機率預測器
    pred = predict_stock_alpha("2330", feats)
    print(f"\n[3] 機器學習 Alpha 預測機率: P_alpha = {pred.p_alpha:.1%}")
    print(f"  高確信進場 (P >= 65%): {pred.is_high_conviction}")
    print(f"  預估期望報酬: {pred.predicted_return_pct:+.2f}%")
    print(f"  主要正向特徵: {', '.join(pred.top_contributing_factors)}")
    if pred.risk_factors:
        print(f"  潛在風險因子: {', '.join(pred.risk_factors)}")
    print(f"  投資建議評級: {pred.recommendation}")

    print("\n" + "=" * 70)
    print("✅ 微觀特徵與 ML 預測流水線測試完成！")
    print("=" * 70)


if __name__ == "__main__":
    test_microstructure_pipeline()
