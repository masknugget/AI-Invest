"""
日志类型定义
"""

from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogType(str, Enum):
    """日志类型"""
    OPERATION = "operation"      # 操作日志
    AUDIT = "audit"              # 审计日志
    SYSTEM = "system"            # 系统日志
    ACCESS = "access"            # 访问日志
    ERROR = "error"              # 错误日志
    BEHAVIOR = "behavior"        # 行为日志
    SECURITY = "security"        # 安全日志


class LogTypeConfig(BaseModel):
    """日志类型配置"""
    retention_days: int = Field(30, description="保留天数")
    archive_enabled: bool = Field(True, description="是否启用归档")
    compress: bool = Field(True, description="是否压缩归档")
    index_fields: list = Field(default_factory=list, description="索引字段")
    alert_enabled: bool = Field(False, description="是否启用告警")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "retention_days": 90,
                    "archive_enabled": True,
                    "compress": True,
                    "index_fields": ["timestamp", "user_id", "action"],
                    "alert_enabled": False
                }
            ]
        }
    }


# 默认日志类型配置
DEFAULT_LOG_TYPE_CONFIGS: Dict[str, LogTypeConfig] = {
    LogType.OPERATION: LogTypeConfig(
        retention_days=90,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "user_id", "action_type", "success"],
        alert_enabled=False
    ),
    LogType.AUDIT: LogTypeConfig(
        retention_days=365,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "user_id", "audit_type", "resource_type"],
        alert_enabled=True
    ),
    LogType.SYSTEM: LogTypeConfig(
        retention_days=30,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "level", "module"],
        alert_enabled=True
    ),
    LogType.ACCESS: LogTypeConfig(
        retention_days=30,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "user_id", "path", "status_code"],
        alert_enabled=False
    ),
    LogType.ERROR: LogTypeConfig(
        retention_days=180,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "error_type", "is_resolved"],
        alert_enabled=True
    ),
    LogType.BEHAVIOR: LogTypeConfig(
        retention_days=60,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "user_id", "behavior_type"],
        alert_enabled=False
    ),
    LogType.SECURITY: LogTypeConfig(
        retention_days=365,
        archive_enabled=True,
        compress=True,
        index_fields=["timestamp", "threat_type", "severity", "source_ip"],
        alert_enabled=True
    ),
}


# 日志级别优先级（用于过滤）
LOG_LEVEL_PRIORITY = {
    LogLevel.DEBUG: 0,
    LogLevel.INFO: 1,
    LogLevel.WARNING: 2,
    LogLevel.ERROR: 3,
    LogLevel.CRITICAL: 4
}


def should_log(min_level: LogLevel, current_level: LogLevel) -> bool:
    """判断是否应该记录日志"""
    return LOG_LEVEL_PRIORITY.get(current_level, 0) >= LOG_LEVEL_PRIORITY.get(min_level, 0)
