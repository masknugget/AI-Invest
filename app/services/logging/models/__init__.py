"""
日志模型模块
"""

from .log_types import LogLevel, LogType, LogTypeConfig
from .log_entry import (
    LogEntry,
    AuditLogEntry,
    ErrorLogEntry,
    AccessLogEntry,
    BehaviorLogEntry,
    SystemLogEntry
)
from .log_stats import (
    LogStats,
    UserActivityStats,
    SecurityStats,
    SystemHealthStats,
    LogTrend
)

__all__ = [
    # 日志类型
    "LogLevel",
    "LogType",
    "LogTypeConfig",
    # 日志条目
    "LogEntry",
    "AuditLogEntry",
    "ErrorLogEntry",
    "AccessLogEntry",
    "BehaviorLogEntry",
    "SystemLogEntry",
    # 统计模型
    "LogStats",
    "UserActivityStats",
    "SecurityStats",
    "SystemHealthStats",
    "LogTrend",
]
