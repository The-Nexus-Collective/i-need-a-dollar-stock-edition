"""
Market Hours Manager - Handle US stock market trading hours

Features:
- Regular hours: 9:30 AM - 4:00 PM ET
- Weekend detection
- Flatten-at-close timing
- Next market open calculation
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

import pytz

logger = logging.getLogger(__name__)


@dataclass
class MarketStatus:
    """Current market status"""
    is_open: bool
    current_time: datetime
    market_timezone: str
    
    # Timing info
    time_to_open: Optional[timedelta] = None
    time_to_close: Optional[timedelta] = None
    
    # Flatten signal
    should_flatten: bool = False
    flatten_reason: Optional[str] = None
    
    # Display
    status_text: str = ""
    next_event: str = ""
    
    def to_dict(self) -> dict:
        return {
            "is_open": self.is_open,
            "current_time": self.current_time.isoformat(),
            "timezone": self.market_timezone,
            "time_to_open_seconds": self.time_to_open.total_seconds() if self.time_to_open else None,
            "time_to_close_seconds": self.time_to_close.total_seconds() if self.time_to_close else None,
            "should_flatten": self.should_flatten,
            "flatten_reason": self.flatten_reason,
            "status_text": self.status_text,
            "next_event": self.next_event,
        }


class MarketHoursManager:
    """
    Manages US stock market trading hours.
    
    Regular Trading Hours:
    - Open: 9:30 AM ET
    - Close: 4:00 PM ET
    - Days: Monday - Friday
    
    Extended Hours (not currently used):
    - Pre-market: 4:00 AM - 9:30 AM ET
    - After-hours: 4:00 PM - 8:00 PM ET
    """
    
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    TZ = pytz.timezone("US/Eastern")
    
    # Flatten this many seconds before close
    FLATTEN_BUFFER_SECONDS = 300  # 5 minutes
    
    # US Market Holidays (2024-2026) - simplified list
    HOLIDAYS = {
        # 2024
        datetime(2024, 1, 1),   # New Year's Day
        datetime(2024, 1, 15),  # MLK Day
        datetime(2024, 2, 19),  # Presidents Day
        datetime(2024, 3, 29),  # Good Friday
        datetime(2024, 5, 27),  # Memorial Day
        datetime(2024, 6, 19),  # Juneteenth
        datetime(2024, 7, 4),   # Independence Day
        datetime(2024, 9, 2),   # Labor Day
        datetime(2024, 11, 28), # Thanksgiving
        datetime(2024, 12, 25), # Christmas
        # 2025
        datetime(2025, 1, 1),
        datetime(2025, 1, 20),
        datetime(2025, 2, 17),
        datetime(2025, 4, 18),
        datetime(2025, 5, 26),
        datetime(2025, 6, 19),
        datetime(2025, 7, 4),
        datetime(2025, 9, 1),
        datetime(2025, 11, 27),
        datetime(2025, 12, 25),
        # 2026
        datetime(2026, 1, 1),
        datetime(2026, 1, 19),
        datetime(2026, 2, 16),
        datetime(2026, 4, 3),
        datetime(2026, 5, 25),
        datetime(2026, 6, 19),
        datetime(2026, 7, 3),
        datetime(2026, 9, 7),
        datetime(2026, 11, 26),
        datetime(2026, 12, 25),
    }
    
    def __init__(self):
        self._last_status: Optional[MarketStatus] = None
    
    def _now_et(self) -> datetime:
        """Get current time in Eastern timezone"""
        return datetime.now(self.TZ)
    
    def _is_holiday(self, date: datetime) -> bool:
        """Check if date is a market holiday"""
        date_only = datetime(date.year, date.month, date.day)
        return date_only in self.HOLIDAYS
    
    def _is_weekend(self, date: datetime) -> bool:
        """Check if date is a weekend"""
        return date.weekday() >= 5
    
    def _is_trading_day(self, date: datetime) -> bool:
        """Check if date is a valid trading day"""
        return not self._is_weekend(date) and not self._is_holiday(date)
    
    def is_market_open(self) -> bool:
        """Check if regular market hours are currently active"""
        now = self._now_et()
        
        # Check if trading day
        if not self._is_trading_day(now):
            return False
        
        # Check time
        current_time = now.time()
        return self.MARKET_OPEN <= current_time < self.MARKET_CLOSE
    
    def get_status(self) -> MarketStatus:
        """Get comprehensive market status"""
        now = self._now_et()
        is_open = self.is_market_open()
        
        status = MarketStatus(
            is_open=is_open,
            current_time=now,
            market_timezone="US/Eastern",
        )
        
        if is_open:
            # Calculate time to close
            close_dt = now.replace(
                hour=self.MARKET_CLOSE.hour,
                minute=self.MARKET_CLOSE.minute,
                second=0,
                microsecond=0
            )
            status.time_to_close = close_dt - now
            
            # Check flatten signal
            if status.time_to_close.total_seconds() <= self.FLATTEN_BUFFER_SECONDS:
                status.should_flatten = True
                status.flatten_reason = f"Market closes in {int(status.time_to_close.total_seconds())}s"
            
            status.status_text = "Market Open"
            minutes_left = int(status.time_to_close.total_seconds() / 60)
            status.next_event = f"Closes in {minutes_left}m"
        else:
            # Calculate time to next open
            next_open = self._get_next_open(now)
            status.time_to_open = next_open - now
            
            # Determine why closed
            if self._is_weekend(now):
                status.status_text = "Weekend - Market Closed"
            elif self._is_holiday(now):
                status.status_text = "Holiday - Market Closed"
            elif now.time() < self.MARKET_OPEN:
                status.status_text = "Pre-Market"
            else:
                status.status_text = "After Hours"
            
            hours_to_open = int(status.time_to_open.total_seconds() / 3600)
            if hours_to_open > 24:
                days = hours_to_open // 24
                status.next_event = f"Opens in {days}d"
            else:
                status.next_event = f"Opens in {hours_to_open}h"
        
        self._last_status = status
        return status
    
    def _get_next_open(self, from_time: datetime) -> datetime:
        """Get the next market open datetime"""
        candidate = from_time
        
        # If before today's open and today is a trading day
        if self._is_trading_day(candidate) and candidate.time() < self.MARKET_OPEN:
            return candidate.replace(
                hour=self.MARKET_OPEN.hour,
                minute=self.MARKET_OPEN.minute,
                second=0,
                microsecond=0
            )
        
        # Move to next day and find trading day
        candidate = candidate + timedelta(days=1)
        while not self._is_trading_day(candidate):
            candidate = candidate + timedelta(days=1)
            if (candidate - from_time).days > 10:
                # Safety: don't loop forever
                break
        
        return candidate.replace(
            hour=self.MARKET_OPEN.hour,
            minute=self.MARKET_OPEN.minute,
            second=0,
            microsecond=0
        )
    
    def should_flatten(self) -> bool:
        """Check if positions should be flattened (close approaching)"""
        status = self.get_status()
        return status.should_flatten
    
    def should_run_cycle(self, last_run: Optional[datetime] = None) -> bool:
        """
        Check if a trading cycle should run.
        
        Cycles run:
        - Only during market hours
        - Every 4 hours (240 minutes)
        - At specific times: 9:30, 13:30 (if within hours)
        """
        if not self.is_market_open():
            return False
        
        if last_run is None:
            return True
        
        now = self._now_et()
        last_run_et = last_run.astimezone(self.TZ) if last_run.tzinfo else self.TZ.localize(last_run)
        
        # Run if 4 hours have passed
        if (now - last_run_et).total_seconds() >= 240 * 60:
            return True
        
        return False
    
    def get_trading_window_info(self) -> dict:
        """Get info about current trading window for logging"""
        status = self.get_status()
        return {
            "is_open": status.is_open,
            "status": status.status_text,
            "next_event": status.next_event,
            "should_flatten": status.should_flatten,
            "current_time_et": status.current_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_market_hours_manager: Optional[MarketHoursManager] = None


def get_market_hours_manager() -> MarketHoursManager:
    """Get or create global market hours manager"""
    global _market_hours_manager
    if _market_hours_manager is None:
        _market_hours_manager = MarketHoursManager()
    return _market_hours_manager

