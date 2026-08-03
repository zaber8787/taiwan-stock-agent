# File: db/paper_trader.py

'''
Paper Trading Engine with Dynamic Capital Allocation and Friction Cost Calculations.
Supports persistent account state in MongoDB with automatic local JSON fallback.
'''
from __future__ import annotations
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '1000000'))
_MAX_ALLOCATION_PCT = float(os.getenv('MAX_CAPITAL_ALLOCATION_PCT', '0.20'))
_COMMISSION_RATE = 0.001425
_STAMP_TAX_RATE = 0.003

_LOCAL_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
_LOCAL_STORAGE_FILE = os.path.join(_LOCAL_DATA_DIR, 'paper_account.json')
_instance: PaperTrader | None = None


class PaperTrader:
    '''Simulated Trading & Capital Risk Management Engine.'''

    def __init__(self, initial_capital: float = _INITIAL_CAPITAL) -> None:
        self.initial_capital = initial_capital
        self.portfolio_id = 'default'
        os.makedirs(_LOCAL_DATA_DIR, exist_ok=True)
        self._load_state()

    def _load_state(self) -> None:
        '''Load portfolio state from MongoDB or fallback to local JSON.'''
        self.state = {
            'portfolio_id': self.portfolio_id,
            'cash': self.initial_capital,
            'initial_capital': self.initial_capital,
            'holdings': {},       # e.g. {'2330': {'shares': 1000, 'cost_price': 950.0}}
            'realized_pnl': 0.0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        self.trades: list[dict[str, Any]] = []

        # Try loading from MongoDB
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

        # Fallback to local JSON file
        if os.path.exists(_LOCAL_STORAGE_FILE):
            try:
                with open(_LOCAL_STORAGE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.state = data.get('state', self.state)
                    self.trades = data.get('trades', [])
            except Exception as e:
                logger.warning(f'Failed to read local paper account file: {e}')

    def _save_state(self) -> None:
        '''Persist portfolio state to MongoDB and local JSON fallback.'''
        self.state['updated_at'] = datetime.now().isoformat()

        # Try MongoDB
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

        # Always update local JSON file
        try:
            with open(_LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
                json.dump({'state': self.state, 'trades': self.trades}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f'Failed to save local paper account file: {e}')

    def reset_account(self, capital: float | None = None) -> dict[str, Any]:
        '''Reset simulation account balance and clear holdings.'''
        capital = capital or self.initial_capital
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
        self._save_state()
        return self.get_account_summary()

    def calculate_allocation(self, ticker: str, current_price: float, confidence: float = 0.5) -> dict[str, Any]:
        '''
        Calculate confidence-weighted capital allocation and max purchasable shares.
        Formula: Budget = Available Cash * MAX_CAPITAL_ALLOCATION_PCT * confidence
        '''
        available_cash = self.state['cash']
        confidence = min(max(confidence, 0.0), 1.0)
        max_pct = _MAX_ALLOCATION_PCT
        
        budget = available_cash * max_pct * confidence
        cost_per_lot = current_price * 1000 if current_price > 0 else 0
        
        suggested_lots = int(budget / cost_per_lot) if cost_per_lot > 0 else 0
        suggested_shares = suggested_lots * 1000
        
        required_cash = suggested_shares * current_price * (1 + _COMMISSION_RATE)
        can_afford = available_cash >= required_cash and suggested_shares >= 1000

        return {
            'ticker': ticker,
            'available_cash': round(available_cash, 2),
            'max_allocation_pct': max_pct,
            'confidence': confidence,
            'budget': round(budget, 2),
            'budget_pct_of_cash': round((budget / available_cash * 100) if available_cash > 0 else 0, 2),
            'current_price': current_price,
            'suggested_shares': suggested_shares,
            'suggested_lots': suggested_lots,
            'can_afford': can_afford
        }

    def execute_signal(self, signal: dict[str, Any], current_price: float = 0.0) -> dict[str, Any]:
        '''Execute BUY / SELL simulated order based on TradeSignal and market price.'''
        ticker = signal.get('ticker', '').upper().replace('.TW', '')
        side = signal.get('side', 'HOLD').upper()
        confidence = float(signal.get('confidence', 0.5))
        reason = signal.get('reason', '')
        current_price = current_price or float(signal.get('price_target', 0.0) or 100.0)

        if not ticker or current_price <= 0:
            return {'status': 'SKIPPED', 'reason': 'Invalid ticker or price'}

        if side == 'BUY':
            alloc = self.calculate_allocation(ticker, current_price, confidence)
            shares = alloc['suggested_shares']
            if shares < 1000 or not alloc['can_afford']:
                return {
                    'status': 'REJECTED',
                    'reason': f"Insufficient cash (available ${self.state['cash']:,.2f}, budget ${alloc['budget']:,.2f}) to buy 1 lot of {ticker} at ${current_price}"
                }

            trade_value = shares * current_price
            commission = max(20.0, round(trade_value * _COMMISSION_RATE, 2))
            total_cost = trade_value + commission

            if self.state['cash'] < total_cost:
                return {'status': 'REJECTED', 'reason': 'Cash balance too low to cover commission'}

            # Update holdings
            self.state['cash'] -= total_cost
            curr_holding = self.state['holdings'].get(ticker, {'shares': 0, 'cost_price': 0.0})
            old_shares = curr_holding['shares']
            old_cost = curr_holding['cost_price'] * old_shares
            new_shares = old_shares + shares
            new_cost_price = (old_cost + total_cost) / new_shares if new_shares > 0 else 0.0

            self.state['holdings'][ticker] = {
                'shares': new_shares,
                'cost_price': round(new_cost_price, 2)
            }

            trade_record = {
                'trade_id': str(uuid.uuid4())[:8],
                'time': datetime.now().isoformat(),
                'ticker': ticker,
                'side': 'BUY',
                'price': current_price,
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
                'price': current_price,
                'total_cost': round(total_cost, 2),
                'trade_id': trade_record['trade_id']
            }

        elif side == 'SELL':
            curr_holding = self.state['holdings'].get(ticker)
            if not curr_holding or curr_holding['shares'] <= 0:
                return {'status': 'REJECTED', 'reason': f"No holdings for {ticker} to sell"}

            shares = curr_holding['shares']
            cost_price = curr_holding['cost_price']
            trade_value = shares * current_price
            commission = max(20.0, round(trade_value * _COMMISSION_RATE, 2))
            stamp_tax = round(trade_value * _STAMP_TAX_RATE, 2)
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
                'price': current_price,
                'shares': shares,
                'net_revenue': round(net_revenue, 2),
                'commission': commission,
                'stamp_tax': stamp_tax,
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
                'price': current_price,
                'net_revenue': round(net_revenue, 2),
                'realized_pnl': round(pnl, 2),
                'trade_id': trade_record['trade_id']
            }

        return {'status': 'SKIPPED', 'reason': 'Signal is HOLD'}

    def get_account_summary(self, price_quotes: dict[str, float] | None = None) -> dict[str, Any]:
        '''Return complete portfolio summary with unrealized and total PnL.'''
        price_quotes = price_quotes or {}
        holdings_value = 0.0
        unrealized_pnl = 0.0
        formatted_holdings = []

        for ticker, info in self.state['holdings'].items():
            shares = info['shares']
            cost_price = info['cost_price']
            market_price = price_quotes.get(ticker, cost_price)
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
                'unrealized_pnl_pct': round(pnl_pct, 2)
            })

        cash = self.state['cash']
        total_equity = cash + holdings_value
        total_roi_pct = ((total_equity - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0.0

        return {
            'portfolio_id': self.portfolio_id,
            'initial_capital': self.initial_capital,
            'cash': round(cash, 2),
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
    '''Return singleton PaperTrader instance.'''
    global _instance
    if _instance is None:
        _instance = PaperTrader()
    return _instance
