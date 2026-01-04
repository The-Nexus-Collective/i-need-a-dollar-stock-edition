"""
Health Tracker - Captures all logged errors and tracks service health.

This module provides:
1. A custom logging handler that captures ERROR and WARNING logs
2. A singleton tracker that stores recent errors and service status
3. Methods to query health status for the API endpoint
"""

import logging
import threading
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Literal

# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LogEntry:
    """A captured log entry."""
    timestamp: str
    level: str
    logger: str
    service: str
    message: str
    module: str
    line: int
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class ServiceStatus:
    """Status of a service."""
    name: str
    status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    last_check: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "status": self.status,
            "last_check": self.last_check,
        }
        if self.error:
            result["error"] = self.error
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        return result


@dataclass
class HealthReport:
    """Complete health report."""
    overall: Literal["healthy", "degraded", "unhealthy"]
    services: Dict[str, dict]
    error_count: int
    warning_count: int
    recent_errors: List[dict]
    last_check: str
    
    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class _HealthLogHandler(logging.Handler):
    """
    Custom logging handler that captures ERROR and WARNING logs.
    
    This handler is installed on the root logger to capture all error
    and warning messages across the entire application.
    """
    
    def __init__(self, tracker: 'HealthTracker'):
        super().__init__()
        self.tracker = tracker
        self.setLevel(logging.WARNING)  # Capture WARNING and above
    
    def emit(self, record: logging.LogRecord):
        """Capture the log record."""
        try:
            # Extract service name from logger name
            # e.g., "core.strategy" -> "strategy", "backend.bot" -> "bot"
            logger_name = record.name
            parts = logger_name.split('.')
            service = parts[-1] if parts else logger_name
            
            # Create log entry
            entry = LogEntry(
                timestamp=datetime.utcnow().isoformat() + "Z",
                level=record.levelname,
                logger=logger_name,
                service=service,
                message=record.getMessage(),
                module=record.filename,
                line=record.lineno,
            )
            
            self.tracker._add_entry(entry)
            
        except Exception:
            # Don't let logging errors crash the application
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH TRACKER SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

class HealthTracker:
    """
    Singleton that captures all logged errors and tracks service health.
    
    Features:
    - Captures all ERROR and WARNING logs via custom handler
    - Stores last 100 log entries in thread-safe deque
    - Tracks service connectivity status
    - Provides health report for API endpoint
    """
    
    _instance: Optional['HealthTracker'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._errors: deque = deque(maxlen=100)
        self._services: Dict[str, ServiceStatus] = {}
        self._entry_lock = threading.Lock()
        self._service_lock = threading.Lock()
        self._error_count = 0
        self._warning_count = 0
        self._handler: Optional[_HealthLogHandler] = None
        self._initialized = True
    
    def get_logging_handler(self) -> logging.Handler:
        """
        Get the logging handler to install on the root logger.
        
        Usage:
            tracker = get_health_tracker()
            logging.getLogger().addHandler(tracker.get_logging_handler())
        """
        if self._handler is None:
            self._handler = _HealthLogHandler(self)
        return self._handler
    
    def _add_entry(self, entry: LogEntry):
        """Add a log entry (called by the handler)."""
        with self._entry_lock:
            self._errors.append(entry)
            if entry.level == "ERROR":
                self._error_count += 1
            elif entry.level == "WARNING":
                self._warning_count += 1
    
    def get_recent_errors(self, limit: int = 50) -> List[LogEntry]:
        """Get the most recent error/warning log entries."""
        with self._entry_lock:
            # Return newest first
            entries = list(self._errors)
            entries.reverse()
            return entries[:limit]
    
    def get_error_count(self) -> int:
        """Get total error count since startup."""
        with self._entry_lock:
            return self._error_count
    
    def get_warning_count(self) -> int:
        """Get total warning count since startup."""
        with self._entry_lock:
            return self._warning_count
    
    def update_service(
        self, 
        name: str, 
        status: Literal["healthy", "unhealthy", "unknown"],
        error: Optional[str] = None,
        latency_ms: Optional[float] = None
    ):
        """
        Update the status of a service.
        
        Args:
            name: Service name (e.g., "database", "redis", "binance", "grok")
            status: Current status
            error: Error message if unhealthy
            latency_ms: Response time in milliseconds
        """
        with self._service_lock:
            self._services[name] = ServiceStatus(
                name=name,
                status=status,
                error=error,
                latency_ms=latency_ms,
                last_check=datetime.utcnow().isoformat() + "Z"
            )
    
    def get_service_status(self, name: str) -> Optional[ServiceStatus]:
        """Get status of a specific service."""
        with self._service_lock:
            return self._services.get(name)
    
    def get_all_services(self) -> Dict[str, ServiceStatus]:
        """Get status of all tracked services."""
        with self._service_lock:
            return dict(self._services)
    
    def get_health_report(self, error_limit: int = 20) -> HealthReport:
        """
        Generate a complete health report.
        
        Returns a HealthReport with:
        - overall: "healthy", "degraded", or "unhealthy"
        - services: Dict of service statuses
        - error_count: Total errors since startup
        - warning_count: Total warnings since startup
        - recent_errors: List of recent log entries
        - last_check: Timestamp of this report
        """
        services = self.get_all_services()
        recent = self.get_recent_errors(error_limit)
        
        # Determine overall status
        unhealthy_count = sum(
            1 for s in services.values() 
            if s.status == "unhealthy"
        )
        recent_errors = sum(
            1 for e in recent 
            if e.level == "ERROR"
        )
        
        if unhealthy_count > 0 or recent_errors >= 10:
            overall = "unhealthy"
        elif recent_errors > 0 or any(s.status == "unknown" for s in services.values()):
            overall = "degraded"
        else:
            overall = "healthy"
        
        return HealthReport(
            overall=overall,
            services={name: s.to_dict() for name, s in services.items()},
            error_count=self.get_error_count(),
            warning_count=self.get_warning_count(),
            recent_errors=[e.to_dict() for e in recent],
            last_check=datetime.utcnow().isoformat() + "Z"
        )
    
    def clear(self):
        """Clear all tracked data (mainly for testing)."""
        with self._entry_lock:
            self._errors.clear()
            self._error_count = 0
            self._warning_count = 0
        with self._service_lock:
            self._services.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_tracker: Optional[HealthTracker] = None


def get_health_tracker() -> HealthTracker:
    """
    Get the global HealthTracker singleton.
    
    Usage:
        from core.health_tracker import get_health_tracker
        
        tracker = get_health_tracker()
        logging.getLogger().addHandler(tracker.get_logging_handler())
    """
    global _tracker
    if _tracker is None:
        _tracker = HealthTracker()
    return _tracker


def install_health_logging():
    """
    Install the health tracking logging handler on the root logger.
    
    Call this once at application startup to enable automatic
    capture of all ERROR and WARNING logs.
    
    Usage:
        from core.health_tracker import install_health_logging
        install_health_logging()
    """
    tracker = get_health_tracker()
    root_logger = logging.getLogger()
    
    # Avoid adding duplicate handlers
    for handler in root_logger.handlers:
        if isinstance(handler, _HealthLogHandler):
            return
    
    root_logger.addHandler(tracker.get_logging_handler())

