# File: app/market_hours.py

'''
Taiwan Stock Market Hours Aware Engine.
Handles Taiwan stock market trading hours:
- Regular trading: Mon-Fri 09:00 - 13:30 (TWD time)
- Call auction: 08:50 - 09:00 (only 08:50-08:59 accepts orders, 09:00-09:02 match)
- Last call: 13:28 - 13:30 (match at 13:30)
- Weekends and holidays: Closed
'''
from __future__ import annotations
import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

# TWSE Trading Hours: Mon-Fri 09:00:00 - 13:30:00 (TWD time)
_MARKET_OPEN_TIME = time(9, 0, 0)
_MARKET_CLOSE_TIME = time(13, 30, 0)
_CALL_AUCTION_START = time(8, 50, 0)
_CALL_AUCTION_END = time(9, 2, 0)
_LAST_CALL_START = time(13, 28, 0)
_DEFERRED_OPEN_OFFSET_MINUTES = 5  # Evaluate at 09:05:00 on next open day

# 台灣國定假日 (簡易版本，實際需查詢 TWSE 假日曆)
_TAIWAN_HOLIDAYS = {
    # 新年
    (1, 1), (1, 2), (1, 3),
    # 春節 (農曆，需手動更新)
    (1, 21), (1, 22), (1, 23), (1, 24), (1, 25), (1, 26), (1, 27),
    # 清明節
    (4, 4), (4, 5), (4, 6),
    # 端午節
    (6, 8), (6, 9), (6, 10),
    # 中秋節
    (9, 17), (9, 18), (9, 19),
    # 國慶日
    (10, 10),
    # 農曆除夕
    (1, 28),
}


def is_market_open(dt: datetime | None = None) -> bool:
    '''Check if Taiwan Stock Market is currently open.
    
    Taiwan Stock Market Hours:
    - Regular trading: Mon-Fri 09:00 - 13:30 (TWD time)
    - Closed on weekends and national holidays
    '''
    dt = dt or datetime.now()
    
    # Weekends (5 = Saturday, 6 = Sunday)
    if dt.weekday() >= 5:
        return False
    
    # Check if it's a national holiday
    if is_taiwan_holiday(dt):
        return False
    
    current_time = dt.time()
    return _MARKET_OPEN_TIME <= current_time <= _MARKET_CLOSE_TIME


def is_taiwan_holiday(dt: datetime) -> bool:
    '''Check if date is a Taiwan national holiday (simplified version).
    
    Note: For accurate holiday checking, use TWSE official holiday calendar.
    '''
    return (dt.month, dt.day) in _TAIWAN_HOLIDAYS


def is_call_auction_time(dt: datetime | None = None) -> bool:
    '''Check if currently in call auction period.
    
    Call auction times:
    - Morning: 08:50 - 09:02 (orders 08:50-08:59, matching 09:00-09:02)
    - Afternoon: 13:28 - 13:30 (matching at 13:30)
    '''
    dt = dt or datetime.now()
    if dt.weekday() >= 5 or is_taiwan_holiday(dt):
        return False
    
    current_time = dt.time()
    morning_call = _CALL_AUCTION_START <= current_time <= _CALL_AUCTION_END
    afternoon_call = _LAST_CALL_START <= current_time <= _MARKET_CLOSE_TIME
    
    return morning_call or afternoon_call


def get_seconds_until_next_market_open(dt: datetime | None = None) -> int:
    '''Calculate seconds until next Taiwan Stock Market initial opening (09:05:00).
    
    Handles weekends and holidays.
    '''
    dt = dt or datetime.now()
    target_date = dt.date()
    
    # If today after close, weekend, or holiday, push to next open day
    if dt.time() > _MARKET_CLOSE_TIME or dt.weekday() >= 5 or is_taiwan_holiday(dt):
        target_date += timedelta(days=1)
        while target_date.weekday() >= 5 or is_taiwan_holiday(target_date):
            target_date += timedelta(days=1)
    elif dt.time() < _MARKET_OPEN_TIME:
        # Today before open
        if is_taiwan_holiday(dt):
            target_date += timedelta(days=1)
            while target_date.weekday() >= 5 or is_taiwan_holiday(target_date):
                target_date += timedelta(days=1)

    target_datetime = datetime.combine(target_date, time(9, _DEFERRED_OPEN_OFFSET_MINUTES, 0))
    if target_datetime <= dt:
        target_date += timedelta(days=1)
        while target_date.weekday() >= 5 or is_taiwan_holiday(target_date):
            target_date += timedelta(days=1)
        target_datetime = datetime.combine(target_date, time(9, _DEFERRED_OPEN_OFFSET_MINUTES, 0))

    delta_seconds = int((target_datetime - dt).total_seconds())
    return max(delta_seconds, 10)


def get_market_status(dt: datetime | None = None) -> dict[str, any]:
    '''Get detailed market status information.
    
    Returns:
        dict with market status details including:
        - is_open: bool
        - is_call_auction: bool
        - seconds_to_open: int (if closed)
        - seconds_to_close: int (if open)
    '''
    dt = dt or datetime.now()
    is_open = is_market_open(dt)
    is_call_auction = is_call_auction_time(dt)
    
    result = {
        'is_open': is_open,
        'is_call_auction': is_call_auction,
        'current_time': dt.isoformat(),
    }
    
    if is_open:
        seconds_to_close = int((datetime.combine(dt.date(), _MARKET_CLOSE_TIME) - dt).total_seconds())
        result['seconds_to_close'] = max(seconds_to_close, 0)
    else:
        result['seconds_to_open'] = get_seconds_until_next_market_open(dt)
    
    return result
