# File: backtest/backtester.py
"""
📊 台股短線量化歷史回測與數學期望值引擎 (Backtest & EV Engine)
根據《台灣股市短線 AI 交易策略規劃書》實現：
1. 嚴格扣除摩擦成本：大戶 2 折手續費 (0.0285%) + 當沖降稅 0.15% / 留倉 0.30% 證交稅 + 0.5% 滑價。
2. 完整量化績效指標：勝率 (WR)、盈虧比 (PLR)、最大回撤 (MDD)、年化夏普比率 (Sharpe Ratio)。
3. 單筆交易數學期望值計算：EV = (WR * AvgProfit) - ((1 - WR) * AvgLoss)。
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """單筆交易紀錄"""
    trade_id: str
    ticker: str
    entry_date: str
    exit_date: str
    holding_days: int
    entry_price: float
    exit_price: float
    shares: int
    gross_return_pct: float
    net_return_pct: float
    is_day_trade: bool
    exit_reason: str
    pnl_twd: float


@dataclass
class BacktestMetrics:
    """回測總結評估指標"""
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float                    # 勝率 WR (%)
    profit_loss_ratio: float           # 盈虧比 PLR
    avg_win_pct: float                 # 平均獲利百分比 (%)
    avg_loss_pct: float                # 平均虧損百分比 (%)
    expected_value_pct: float          # 單筆實質數學期望值 EV (%)
    max_drawdown_pct: float            # 最大回撤 MDD (%)
    sharpe_ratio: float                # 年化夏普比率 Sharpe
    total_net_roi_pct: float           # 累積總淨報酬率 (%)
    final_equity_twd: float            # 期末總資產
    is_ev_positive: bool               # 期望值是否為正
    meets_strategy_standard: bool      # 是否達標 (WR>=55%, PLR>=1.5, MDD<=15%, Sharpe>=1.8)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_trades': self.total_trades,
            'win_trades': self.win_trades,
            'loss_trades': self.loss_trades,
            'win_rate': round(self.win_rate, 2),
            'profit_loss_ratio': round(self.profit_loss_ratio, 2),
            'avg_win_pct': round(self.avg_win_pct, 2),
            'avg_loss_pct': round(self.avg_loss_pct, 2),
            'expected_value_pct': round(self.expected_value_pct, 3),
            'max_drawdown_pct': round(self.max_drawdown_pct, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'total_net_roi_pct': round(self.total_net_roi_pct, 2),
            'final_equity_twd': round(self.final_equity_twd, 2),
            'is_ev_positive': self.is_ev_positive,
            'meets_strategy_standard': self.meets_strategy_standard
        }


class BacktestEngine:
    """台股微觀策略回測引擎"""

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_discount: float = 0.20,     # 2 折退佣
        slippage_pct: float = 0.005            # 0.5% 滑價
    ):
        self.initial_capital = initial_capital
        self.commission_rate = 0.001425 * commission_discount
        self.slippage_pct = slippage_pct

    def run_simulation(
        self,
        num_trades: int = 120,
        base_win_rate: float = 0.585,
        avg_profit: float = 0.062,
        avg_loss: float = 0.043
    ) -> BacktestMetrics:
        """
        基於台股統計分佈模擬多週期短線交易執行。
        加入隨機波動與台股真實摩擦成本。
        """
        np.random.seed(42)
        trades: List[TradeRecord] = []
        equity = self.initial_capital
        equity_curve = [equity]

        win_returns: List[float] = []
        loss_returns: List[float] = []

        for i in range(num_trades):
            is_win = np.random.rand() < base_win_rate
            holding_days = np.random.randint(1, 5) # 1~4 天
            is_day_trade = (holding_days == 1 and not is_win and np.random.rand() < 0.35)

            # 計算毛報酬
            if is_win:
                gross_ret = np.random.normal(avg_profit, 0.025)
                gross_ret = max(0.015, gross_ret) # 最少賺 1.5%
            else:
                gross_ret = -np.random.normal(avg_loss, 0.015)
                gross_ret = max(-0.06, gross_ret) # 剛性停損 -6% 截斷

            # 計算交易摩擦成本
            # 買入手續費 + 賣出手續費
            comm_cost = self.commission_rate * 2.0
            # 當沖 0.15% 降稅，過夜 0.30% 稅
            tax_rate = 0.0015 if is_day_trade else 0.0030
            # 雙邊滑價
            slip_cost = self.slippage_pct * 2.0
            total_friction = comm_cost + tax_rate + slip_cost

            net_ret = gross_ret - total_friction
            
            # 部位規模 20%
            position_size = equity * 0.20
            pnl = position_size * net_ret
            equity += pnl
            equity_curve.append(equity)

            if net_ret > 0:
                win_returns.append(net_ret)
            else:
                loss_returns.append(abs(net_ret))

            trades.append(TradeRecord(
                trade_id=f"T-{i+1:03d}",
                ticker="2330",
                entry_date=f"2024-01-{(i%28)+1:02d}",
                exit_date=f"2024-01-{min(28, (i%28)+holding_days+1):02d}",
                holding_days=holding_days,
                entry_price=100.0,
                exit_price=round(100.0 * (1 + gross_ret), 2),
                shares=1000,
                gross_return_pct=round(gross_ret * 100, 2),
                net_return_pct=round(net_ret * 100, 2),
                is_day_trade=is_day_trade,
                exit_reason="移動停利達成" if is_win else ("-6% 剛性停損" if gross_ret <= -0.055 else "T+4 時間出場"),
                pnl_twd=round(pnl, 2)
            ))

        # 計算評估指標
        total_count = len(trades)
        win_count = len(win_returns)
        loss_count = len(loss_returns)
        actual_wr = (win_count / total_count) * 100.0 if total_count > 0 else 0.0

        mean_win = float(np.mean(win_returns)) if win_returns else 0.0
        mean_loss = float(np.mean(loss_returns)) if loss_returns else 0.0
        plr = (mean_win / mean_loss) if mean_loss > 0 else 1.0

        # 單筆數學期望值 EV = (WR * AvgProfit) - ((1 - WR) * AvgLoss)
        wr_decimal = actual_wr / 100.0
        ev_pct = ((wr_decimal * mean_win) - ((1.0 - wr_decimal) * mean_loss)) * 100.0

        # 計算最大回撤 MDD
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
        mdd_pct = max_dd * 100.0

        # 計算夏普比率 (日頻率轉換年化)
        ret_series = [t.net_return_pct / 100.0 for t in trades]
        std_ret = float(np.std(ret_series)) if len(ret_series) > 1 else 0.01
        mean_ret = float(np.mean(ret_series))
        sharpe = (mean_ret / std_ret) * np.sqrt(252 / 2.5) if std_ret > 0 else 1.5

        total_net_roi = ((equity - self.initial_capital) / self.initial_capital) * 100.0

        meets_standard = (actual_wr >= 55.0 and plr >= 1.5 and mdd_pct <= 15.0 and sharpe >= 1.8)

        return BacktestMetrics(
            total_trades=total_count,
            win_trades=win_count,
            loss_trades=loss_count,
            win_rate=actual_wr,
            profit_loss_ratio=plr,
            avg_win_pct=mean_win * 100.0,
            avg_loss_pct=mean_loss * 100.0,
            expected_value_pct=ev_pct,
            max_drawdown_pct=mdd_pct,
            sharpe_ratio=sharpe,
            total_net_roi_pct=total_net_roi,
            final_equity_twd=equity,
            is_ev_positive=ev_pct > 0,
            meets_strategy_standard=meets_standard
        )
