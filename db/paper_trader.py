# File: db/paper_trader.py

'''
Paper Trading Engine with Microstructure Short-Term Strategy Rules:
- 2-Discount Broker Fee (0.0285%)
- Day-Trade Tax Discount (0.15% on intraday stop-loss)
- Hard Intraday Stop Loss (-6%)
- Trailing Stop-Profit (+10% activation / 2% callback)
- Time-Based Exit (T+4 forced liquidation after 3 holding days)
'''
from __future__ import annotations
import os
import json
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Any

from app.market_hours import is_market_open, is_call_auction_time, get_market_status

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '1000000'))
_MAX_ALLOCATION_PCT = float(os.getenv('MAX_CAPITAL_ALLOCATION_PCT', '0.20'))
_MAX_POSITIONS_LIMIT = int(os.getenv('MAX_POSITIONS_LIMIT', '5'))
_MAX_SINGLE_STOCK_PCT = float(os.getenv('MAX_SINGLE_STOCK_PCT', '0.20'))
_MAX_SINGLE_STOCK_LOTS = int(os.getenv('MAX_SINGLE_STOCK_LOTS', '10'))
_MAX_INDUSTRY_PCT = float(os.getenv('MAX_INDUSTRY_PCT', '0.50'))

# 2-Discount Broker Fee (0.1425% * 0.20 = 0.0285%)
_COMMISSION_RATE = 0.001425 * 0.20
_STAMP_TAX_OVERNIGHT = 0.0030
_STAMP_TAX_DAYTRADE = 0.0015

_SLIPPAGE_PCT = 0.005

# Strategy Exit Rules
_HARD_STOP_LOSS_PCT = -0.06            # -6% Hard Stop Loss
_TRAILING_ACTIVATION_PCT = 0.10        # +10% Trailing Stop Activation
_TRAILING_CALLBACK_PCT = 0.02          # 2% Callback from High
_MAX_HOLDING_DAYS = 3                  # Force exit on T+4 (after 3 holding days)

_LOCAL_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
_LOCAL_STORAGE_FILE = os.path.join(_LOCAL_DATA_DIR, 'paper_account.json')
_instance: PaperTrader | None = None

# Industry mapping for concentration checks
_INDUSTRY_MAP = {
    '2330': '半導體', '2454': '半導體', '2303': '半導體', '3008': '半導體',
    '2382': '電腦設備', '3231': '電腦設備', '2317': '電子零組件', '2376': '電子零組件',
    '0050': 'ETF', '0056': 'ETF', '00878': 'ETF', '00919': 'ETF', '00929': 'ETF', '00940': 'ETF'
}


class PaperTrader:
    '''Microstructure Short-Term Strategy Paper Trading Engine.'''

    def __init__(self, initial_capital: float = _INITIAL_CAPITAL) -> None:
        self.initial_capital = initial_capital
        self.portfolio_id = 'default'
        os.makedirs(_LOCAL_DATA_DIR, exist_ok=True)
        self._load_state()

    @staticmethod
    def get_stock_industry(ticker: str) -> str | None:
        '''Get industry for a given ticker.'''
        clean_ticker = ticker.replace('.TW', '')
        return _INDUSTRY_MAP.get(clean_ticker)

    def get_industry_holdings_value(self, ticker: str) -> float:
        '''Calculate total holdings value for the ticker's industry.'''
        industry = self.get_stock_industry(ticker)
        if not industry:
            return 0.0
        
        industry_value = 0.0
        for hold_ticker, info in self.state.get('holdings', {}).items():
            if self.get_stock_industry(hold_ticker) == industry:
                shares = info.get('shares', 0)
                cost_price = info.get('cost_price', 0)
                industry_value += shares * cost_price
        
        return industry_value

    def check_industry_concentration(self, ticker: str, proposed_value: float) -> tuple[float, str]:
        '''
        Check if adding this stock would exceed industry concentration limit.
        Returns (allowed_value, status_message)
        - If within limits: returns (proposed_value, "OK")
        - If exceeds limits: returns (adjusted_value, "Adjusted to X% limit")
        '''
        industry = self.get_stock_industry(ticker)
        if not industry:
            return proposed_value, "No industry classification"
        
        current_industry_value = self.get_industry_holdings_value(ticker)
        proposed_total = current_industry_value + proposed_value
        proposed_pct = proposed_total / self.initial_capital if self.initial_capital > 0 else 0
        
        if proposed_pct > _MAX_INDUSTRY_PCT:
            max_total_by_industry = self.initial_capital * _MAX_INDUSTRY_PCT
            adjusted_value = max(0, max_total_by_industry - current_industry_value)
            return adjusted_value, f"Industry {industry} adjusted to {_MAX_INDUSTRY_PCT*100:.0f}% limit"
        
        return proposed_value, f"Industry {industry} concentration OK ({proposed_pct*100:.1f}%)"

    def check_single_stock_limit(self, ticker: str, proposed_shares: int, price: float) -> tuple[int, str]:
        '''
        Check if proposed position exceeds single stock limits.
        Returns (allowed_shares, status_message)
        - If within limits: returns (proposed_shares, "OK")
        - If exceeds limits: returns (adjusted_shares, "Adjusted to X lots")
        '''
        proposed_value = proposed_shares * price
        proposed_pct = proposed_value / self.initial_capital if self.initial_capital > 0 else 0
        proposed_lots = proposed_shares // 1000
        
        # Limit by max lots
        if proposed_lots > _MAX_SINGLE_STOCK_LOTS:
            adjusted_lots = _MAX_SINGLE_STOCK_LOTS
            adjusted_shares = adjusted_lots * 1000
            return adjusted_shares, f"Adjusted to max {_MAX_SINGLE_STOCK_LOTS} lots ({adjusted_shares} shares)"
        
        # Limit by percentage of capital
        max_value_by_pct = self.initial_capital * _MAX_SINGLE_STOCK_PCT
        if proposed_value > max_value_by_pct:
            max_shares_by_pct = int(max_value_by_pct / price / 1000) * 1000
            # Ensure we also respect the lots limit
            max_lots_by_pct = max_shares_by_pct // 1000
            final_lots = min(max_lots_by_pct, _MAX_SINGLE_STOCK_LOTS)
            adjusted_shares = final_lots * 1000
            return adjusted_shares, f"Adjusted to {_MAX_SINGLE_STOCK_PCT*100:.0f}% capital limit ({adjusted_shares} shares)"
        
        return proposed_shares, f"Within limits ({proposed_lots} lots, {proposed_pct*100:.1f}%)"

    def _load_state(self) -> None:
        self.state = {
            'portfolio_id': self.portfolio_id,
            'cash': self.initial_capital,
            'initial_capital': self.initial_capital,
            'holdings': {},       # e.g. {'2330': {'shares': 1000, 'cost_price': 950.0, 'buy_date': '2026-08-04', 'highest_price': 980.0}}
            'realized_pnl': 0.0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        self.trades: list[dict[str, Any]] = []

        try:
            from db.mongo_client import get_mongo_client
            mc = get_mongo_client()
            doc = mc.find_one('portfolio', {'portfolio_id': self.portfolio_id})
            if doc:
                self.state['cash'] = float(doc.get('cash', self.initial_capital))
                self.state['holdings'] = doc.get('holdings', {})
                self.state['realized_pnl'] = float(doc.get('realized_pnl', 0.0))
                return
        except Exception:
            pass

        if os.path.exists(_LOCAL_STORAGE_FILE):
            try:
                with open(_LOCAL_STORAGE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.state = data.get('state', self.state)
                    self.trades = data.get('trades', [])
            except Exception as e:
                logger.warning(f'Failed to read local paper account file: {e}')

    def _save_state(self) -> None:
        self.state['updated_at'] = datetime.now().isoformat()

        try:
            from db.mongo_client import get_mongo_client
            mc = get_mongo_client()
            mc.update_one(
                'portfolio',
                {'portfolio_id': self.portfolio_id},
                {'$set': self.state},
                upsert=True
            )
        except Exception:
            pass

        try:
            with open(_LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
                json.dump({'state': self.state, 'trades': self.trades}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f'Failed to save local paper account file: {e}')

    def reset_account(self, capital: float | None = None) -> dict[str, Any]:
        '''Perform a 100% total reset of capital, holdings, trade logs, and PnL.'''
        capital = capital or self.initial_capital
        logger.info(f"🧹 [PaperTrader] 執行 100% 完全重置：清除所有股票持倉、歷史交易與 PnL，恢復本金為 ${capital:,.2f}...")

        self.state = {
            'portfolio_id': self.portfolio_id,
            'cash': capital,
            'initial_capital': capital,
            'holdings': {},
            'realized_pnl': 0.0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        self.trades = []

        try:
            from db.mongo_client import get_mongo_client
            mc = get_mongo_client()
            mc.delete_many('portfolio', {'portfolio_id': self.portfolio_id})
            mc.insert_one('portfolio', self.state)
        except Exception:
            pass

        try:
            with open(_LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
                json.dump({'state': self.state, 'trades': []}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Local storage reset warning: {e}")

        return self.get_account_summary()

    def check_position_exit_rules(self, ticker: str, current_price: float) -> dict[str, Any] | None:
        '''
        Evaluate exit rules for active position:
        1. Hard Intraday Stop-Loss (-6%) -> Intraday Day-Trade Tax Discount (0.15%)
        2. Trailing Stop-Profit (+10% activation, 2% callback from highest price)
        3. Time-Based Stop (T+4 liquidation after 3 holding days)
        '''
        clean_ticker = ticker.replace('.TW', '')
        info = self.state['holdings'].get(clean_ticker)
        if not info or current_price <= 0:
            return None

        cost_price = info['cost_price']
        buy_date_str = info.get('buy_date', datetime.now().strftime('%Y-%m-%d'))
        highest_price = max(info.get('highest_price', cost_price), current_price)
        info['highest_price'] = highest_price # Update peak price

        pnl_pct = (current_price - cost_price) / cost_price

        # Rule 1: Hard Intraday Stop Loss (-6%)
        if pnl_pct <= _HARD_STOP_LOSS_PCT:
            is_intraday_today = (buy_date_str == datetime.now().strftime('%Y-%m-%d')) and is_market_open()
            exit_type = "當沖避險剛性停損 (-6% 享 0.15% 降稅)" if is_intraday_today else "剛性過夜停損 (-6%)"
            return {
                'trigger': True,
                'type': 'STOP_LOSS',
                'is_daytrade': is_intraday_today,
                'reason': f"{exit_type} | 報價 ${current_price} (跌幅 {pnl_pct*100:.1f}%)"
            }

        # Rule 2: Trailing Stop Profit (+10% activation, 2% callback from high)
        peak_gain_pct = (highest_price - cost_price) / cost_price
        if peak_gain_pct >= _TRAILING_ACTIVATION_PCT:
            callback_pct = (highest_price - current_price) / highest_price
            if callback_pct >= _TRAILING_CALLBACK_PCT:
                return {
                    'trigger': True,
                    'type': 'TRAILING_STOP',
                    'is_daytrade': False,
                    'reason': f"動態移動停利觸發 (最高點 ${highest_price} 回檔 {callback_pct*100:.1f}%)"
                }

        # Rule 3: Time-Based Stop (T+4 liquidation after 3 holding days)
        try:
            b_date = datetime.strptime(buy_date_str[:10], '%Y-%m-%d').date()
            days_held = (date.today() - b_date).days
            if days_held > _MAX_HOLDING_DAYS:
                return {
                    'trigger': True,
                    'type': 'TIME_STOP',
                    'is_daytrade': False,
                    'reason': f"時間停損 T+4 清倉釋放資金 (已持倉 {days_held} 天)"
                }
        except Exception:
            pass

        return None

    def calculate_allocation(self, ticker: str, current_price: float, confidence: float = 0.5) -> dict[str, Any]:
        available_cash = self.state['cash']
        confidence = min(max(confidence, 0.0), 1.0)
        max_pct = _MAX_ALLOCATION_PCT
        
        budget = available_cash * max_pct * confidence
        cost_per_lot = current_price * (1 + _SLIPPAGE_PCT) * 1000 if current_price > 0 else 0
        
        suggested_lots = int(budget / cost_per_lot) if cost_per_lot > 0 else 0
        suggested_shares = suggested_lots * 1000
        
        required_cash = suggested_shares * current_price * (1 + _SLIPPAGE_PCT) * (1 + _COMMISSION_RATE)
        can_afford = available_cash >= required_cash and suggested_shares >= 1000

        return {
            'ticker': ticker,
            'available_cash': round(available_cash, 2),
            'max_allocation_pct': max_pct,
            'confidence': confidence,
            'budget': round(budget, 2),
            'budget_pct_of_cash': round((budget / available_cash * 100) if available_cash > 0 else 0, 2),
            'current_price': current_price,
            'execution_price_with_slippage': round(current_price * (1 + _SLIPPAGE_PCT), 2),
            'suggested_shares': suggested_shares,
            'suggested_lots': suggested_lots,
            'can_afford': can_afford
        }

    def execute_signal(self, signal: dict[str, Any], current_price: float = 0.0) -> dict[str, Any]:
        ticker = signal.get('ticker', '').upper().replace('.TW', '')
        side = signal.get('side', 'HOLD').upper()
        confidence = float(signal.get('confidence', 0.5))
        reason = signal.get('reason', '')
        
        # 優先使用傳入的 current_price
        if current_price <= 0:
            # 次選：檢查 signal 中的 price_target
            current_price = signal.get('price_target', 0.0)
        
        # 第三選項：自動從 yfinance 抓取當前股價
        if current_price <= 0 and ticker:
            try:
                import yfinance as yf
                stock = yf.Ticker(f"{ticker}.TW")
                hist = stock.history(period='1d')
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
                    logger.info(f"📊 [PaperTrader] 自動抓取 {ticker} 當前股價：${current_price:.2f} (from yfinance)")
            except Exception as e:
                logger.debug(f"📊 [PaperTrader] yfinance 抓取失敗: {e}")
                current_price = 0
        
        if not ticker or current_price <= 0:
            return {'status': 'SKIPPED', 'reason': 'Invalid ticker or price - current_price required and could not be fetched from yfinance'}

        if side == 'BUY':
            current_holdings = self.state['holdings']
            
            # Check positions limit
            if ticker not in current_holdings and len(current_holdings) >= _MAX_POSITIONS_LIMIT:
                logger.info(f"⛔ [PaperTrader] 已達持倉上限 ({_MAX_POSITIONS_LIMIT} 檔)，跳過 {ticker} 買進下單。")
                return {'status': 'SKIPPED', 'reason': f"Max positions limit ({_MAX_POSITIONS_LIMIT} stocks) reached"}

            exec_price = round(current_price * (1 + _SLIPPAGE_PCT), 2)
            alloc = self.calculate_allocation(ticker, current_price, confidence)
            shares = alloc['suggested_shares']

            if shares < 1000 or not alloc['can_afford']:
                logger.info(f"💰 [PaperTrader] 現金不足，跳過 {ticker} (預算 ${alloc['budget']:,.2f}, 需要 ${required_cash:,.2f})")
                return {
                    'status': 'SKIPPED',
                    'reason': f"Insufficient cash (budget ${alloc['budget']:,.2f}, need ${required_cash:,.2f} for 1 lot)"
                }

            # Check single stock limits (auto-adjust if exceeds)
            adjusted_shares, limit_msg = self.check_single_stock_limit(ticker, shares, current_price)
            if adjusted_shares != shares:
                logger.info(f"📊 [PaperTrader] {ticker} 調整購買張數：{shares} → {adjusted_shares} ({limit_msg})")
                shares = adjusted_shares
            
            # Check industry concentration (auto-adjust if exceeds)
            proposed_value = shares * current_price
            adjusted_value, industry_msg = self.check_industry_concentration(ticker, proposed_value)
            if adjusted_value < proposed_value:
                adjusted_shares_for_industry = int(adjusted_value / current_price / 1000) * 1000
                if adjusted_shares_for_industry < shares:
                    logger.info(f"📊 [PaperTrader] {ticker} 因產業集中度調整：{shares} → {adjusted_shares_for_industry} 張 ({industry_msg})")
                    shares = adjusted_shares_for_industry

            trade_value = shares * exec_price
            commission = max(20.0, round(trade_value * _COMMISSION_RATE, 2))
            total_cost = trade_value + commission

            if self.state['cash'] < total_cost:
                logger.info(f"💰 [PaperTrader] 現金不足，跳過 {ticker} (現金 ${self.state['cash']:,.2f} < 需要 ${total_cost:,.2f})")
                return {'status': 'SKIPPED', 'reason': 'Cash balance too low'}

            self.state['cash'] -= total_cost
            curr_holding = current_holdings.get(ticker, {'shares': 0, 'cost_price': 0.0, 'buy_date': datetime.now().strftime('%Y-%m-%d'), 'highest_price': exec_price})
            old_shares = curr_holding['shares']
            old_cost = curr_holding['cost_price'] * old_shares
            new_shares = old_shares + shares
            new_cost_price = (old_cost + total_cost) / new_shares if new_shares > 0 else 0.0

            self.state['holdings'][ticker] = {
                'shares': new_shares,
                'cost_price': round(new_cost_price, 2),
                'buy_date': curr_holding.get('buy_date', datetime.now().strftime('%Y-%m-%d')),
                'highest_price': max(curr_holding.get('highest_price', exec_price), exec_price)
            }

            trade_record = {
                'trade_id': str(uuid.uuid4())[:8],
                'time': datetime.now().isoformat(),
                'ticker': ticker,
                'side': 'BUY',
                'raw_price': current_price,
                'price': exec_price,
                'slippage_pct': _SLIPPAGE_PCT,
                'shares': shares,
                'total_cost': round(total_cost, 2),
                'commission': commission,
                'stamp_tax': 0.0,
                'reason': reason,
                'confidence': confidence
            }
            self.trades.append(trade_record)
            self._save_state()

            return {
                'status': 'EXECUTED',
                'action': 'BUY',
                'ticker': ticker,
                'shares': shares,
                'price': exec_price,
                'total_cost': round(total_cost, 2),
                'trade_id': trade_record['trade_id']
            }

        elif side == 'SELL':
            curr_holding = self.state['holdings'].get(ticker)
            if not curr_holding or curr_holding['shares'] <= 0:
                logger.info(f"📉 [PaperTrader] 無持倉，跳過 {ticker} 賣出下單")
                return {'status': 'SKIPPED', 'reason': f"No holdings for {ticker}"}

            exec_price = round(current_price * (1 - _SLIPPAGE_PCT), 2)
            shares = curr_holding['shares']
            cost_price = curr_holding['cost_price']
            buy_date_str = curr_holding.get('buy_date', datetime.now().strftime('%Y-%m-%d'))
            
            # Day-trade tax discount (0.15%) if bought today, else overnight tax (0.30%)
            is_daytrade = (buy_date_str == datetime.now().strftime('%Y-%m-%d')) and is_market_open()
            tax_rate = _STAMP_TAX_DAYTRADE if is_daytrade else _STAMP_TAX_OVERNIGHT

            trade_value = shares * exec_price
            commission = max(20.0, round(trade_value * _COMMISSION_RATE, 2))
            stamp_tax = round(trade_value * tax_rate, 2)
            net_revenue = trade_value - commission - stamp_tax

            pnl = net_revenue - (cost_price * shares)
            self.state['cash'] += net_revenue
            self.state['realized_pnl'] += pnl
            del self.state['holdings'][ticker]

            trade_record = {
                'trade_id': str(uuid.uuid4())[:8],
                'time': datetime.now().isoformat(),
                'ticker': ticker,
                'side': 'SELL',
                'raw_price': current_price,
                'price': exec_price,
                'slippage_pct': _SLIPPAGE_PCT,
                'shares': shares,
                'net_revenue': round(net_revenue, 2),
                'commission': commission,
                'stamp_tax': stamp_tax,
                'tax_rate_label': '0.15% (當沖降稅)' if is_daytrade else '0.30% (標準證交稅)',
                'realized_pnl': round(pnl, 2),
                'reason': reason,
                'confidence': confidence
            }
            self.trades.append(trade_record)
            self._save_state()

            return {
                'status': 'EXECUTED',
                'action': 'SELL',
                'ticker': ticker,
                'shares': shares,
                'price': exec_price,
                'net_revenue': round(net_revenue, 2),
                'realized_pnl': round(pnl, 2),
                'trade_id': trade_record['trade_id']
            }

        return {'status': 'SKIPPED', 'reason': 'Signal is HOLD'}

    def get_account_summary(self, price_quotes: dict[str, float] | None = None) -> dict[str, Any]:
        price_quotes = price_quotes or {}
        holdings_value = 0.0
        unrealized_pnl = 0.0
        formatted_holdings = []

        for ticker, info in list(self.state['holdings'].items()):
            shares = info['shares']
            cost_price = info['cost_price']
            market_price = price_quotes.get(ticker, cost_price)

            # Auto-eval exit rules for active holdings
            exit_eval = self.check_position_exit_rules(ticker, market_price)
            if exit_eval and exit_eval.get('trigger'):
                logger.info(f"🚨 [PaperTrader Exit Rule] {ticker} 觸發離場訊號: {exit_eval['reason']} -> 自動市價平倉！")
                self.execute_signal({'ticker': ticker, 'side': 'SELL', 'confidence': 1.0, 'reason': exit_eval['reason']}, current_price=market_price)
                continue

            mkt_val = shares * market_price
            item_pnl = mkt_val - (cost_price * shares)
            pnl_pct = (item_pnl / (cost_price * shares) * 100) if cost_price * shares > 0 else 0.0

            holdings_value += mkt_val
            unrealized_pnl += item_pnl

            formatted_holdings.append({
                'ticker': ticker,
                'shares': shares,
                'lots': shares // 1000,
                'cost_price': cost_price,
                'current_price': market_price,
                'market_value': round(mkt_val, 2),
                'unrealized_pnl': round(item_pnl, 2),
                'unrealized_pnl_pct': round(pnl_pct, 2),
                'buy_date': info.get('buy_date', '--'),
                'highest_price': info.get('highest_price', cost_price)
            })

        cash = self.state['cash']
        total_equity = cash + holdings_value
        total_roi_pct = ((total_equity - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0.0

        return {
            'portfolio_id': self.portfolio_id,
            'initial_capital': self.initial_capital,
            'cash': round(cash, 2),
            'max_positions_limit': _MAX_POSITIONS_LIMIT,
            'commission_rate_label': '0.0285% (券商2折合約)',
            'daytrade_tax_label': '0.15% (當沖降稅優惠)',
            'slippage_pct': _SLIPPAGE_PCT,
            'holdings_value': round(holdings_value, 2),
            'total_equity': round(total_equity, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'realized_pnl': round(self.state['realized_pnl'], 2),
            'total_pnl': round(unrealized_pnl + self.state['realized_pnl'], 2),
            'total_roi_pct': round(total_roi_pct, 2),
            'holdings': formatted_holdings,
            'trades_count': len(self.trades)
        }


def get_paper_trader() -> PaperTrader:
    global _instance
    if _instance is None:
        _instance = PaperTrader()
    return _instance
