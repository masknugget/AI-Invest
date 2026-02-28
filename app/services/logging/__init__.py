"""
日志服务模块

完整的日志存储、分析、导出解决方案

使用示例:
    ```python
    from app.services.logging import LogService, LogEntry
    
    # 写入日志
    await LogService.write_log(
        log_type="operation",
        level="info",
        action="user_login",
        message="用户登录成功",
        user_id="admin"
    )
    
    # 查询日志
    logs = await LogService.query_logs(
        user_id="admin",
        days=7
    )
    
    # 导出日志
    result = await LogService.export_logs(
        format="csv",
        days=7
    )
    ```
"""

from .logging_service import LogService, get_log_service
from .models import (
    LogEntry,
    LogLevel,
    LogType,
    AuditLogEntry,
    ErrorLogEntry,
    UserActivityStats,
    SecurityStats,
    ExportResult
)

__all__ = [
    # 服务
    "LogService",
    "get_log_service",
    # 模型
    "LogEntry",
    "LogLevel",
    "LogType",
    "AuditLogEntry",
    "ErrorLogEntry",
    "UserActivityStats",
    "SecurityStats",
    "ExportResult",
]

# 版本号
__version__ = "1.0.0"
