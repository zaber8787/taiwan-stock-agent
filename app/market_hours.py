# File: app/market_hours.py

'''
Taiwan Stock Market Hours Aware Engine.
Handles market opening hours (Mon-Fri 09:00 - 13:30 TWD time)
and calculates deferred seconds for off-market watch timers.
'''
from __future__ import annotations
import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

# TWSE Trading Hours: Mon-Fri 09:00:00 - 13:30:00
_MARKET_OPEN_TIME = time(9, 0, 0)
_MARKET_CLOSE_TIME = time(13, 30, 0)
_DEFERRED_OPEN_OFFSET_MINUTES = 5 # Evaluate at 09:05:00 on next open day


def is_market_open(dt: datetime | None = None) -> bool:
    '''Check if Taiwan Stock Market is currently open.'''
    dt = dt or datetime.now()
    # Weekends (5 = Saturday, 6 = Sunday)
    if dt.weekday() >= 5:
        return False
    current_time = dt.time()
    return _MARKET_OPEN_TIME <= current_time <= _MARKET_CLOSE_TIME


def get_seconds_until_next_market_open(dt: datetime | None = None) -> int:
    '''Calculate seconds until next Taiwan Stock Market initial opening (09:05:00).'''
    dt = dt or datetime.now()
    target_date = dt.date()
    
    # If today after close or weekend, push to next open day
    if dt.time() > _MARKET_CLOSE_TIME or dt.weekday() >= 5:
        target_date += timedelta(days=1)
        while target_date.weekday() >= 5: # Skip Saturday/Sunday
            target_date += timedelta(days=1)
    elif dt.time() < _MARKET_OPEN_TIME:
        # Today before open
        pass

    target_datetime = datetime.combine(target_date, time(9, _DEFERRED_OPEN_OFFSET_MINUTES, 0))
    if target_datetime <= dt:
        target_date += timedelta(days=1)
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)
        target_datetime = datetime.combine(target_date, time(9, _DEFERRED_OPEN_OFFSET_MINUTES, 0))

    delta_seconds = int((target_datetime - dt).total_seconds())
    return max(delta_seconds, 10)
