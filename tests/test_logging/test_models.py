"""
日志模型测试
"""

import pytest
from datetime import datetime
from app.services.logging.models import (
    LogLevel, LogType, LogTypeConfig,
    LogEntry, AuditLogEntry, ErrorLogEntry,
    UserActivityStats, SecurityStats, LogTrend
)


class TestLogTypes:
    """测试日志类型定义"""
    
    def test_log_level_values(self):
        """测试日志级别值"""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"
    
    def test_log_type_values(self):
        """测试日志类型值"""
        assert LogType.OPERATION.value == "operation"
        assert LogType.AUDIT.value == "audit"
        assert LogType.ERROR.value == "error"
        assert LogType.SECURITY.value == "security"
    
    def test_log_type_config_defaults(self):
        """测试日志类型配置默认值"""
        config = LogTypeConfig()
        assert config.retention_days == 30
        assert config.archive_enabled is True
        assert config.compress is True
        assert config.alert_enabled is False
    
    def test_log_type_config_custom(self):
        """测试自定义配置"""
        config = LogTypeConfig(
            retention_days=90,
            archive_enabled=False,
            index_fields=["timestamp", "user_id"]
        )
        assert config.retention_days == 90
        assert config.archive_enabled is False
        assert config.index_fields == ["timestamp", "user_id"]


class TestLogEntry:
    """测试日志条目模型"""
    
    def test_basic_log_entry_creation(self):
        """测试基本日志条目创建"""
        entry = LogEntry(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="user_login",
            message="用户登录成功",
            user_id="admin",
            username="管理员"
        )
        
        assert entry.log_type == LogType.OPERATION
        assert entry.level == LogLevel.INFO
        assert entry.action == "user_login"
        assert entry.user_id == "admin"
        assert entry.archived is False
        assert isinstance(entry.timestamp, datetime)
    
    def test_log_entry_to_mongo_doc(self):
        """测试转换为 MongoDB 文档"""
        entry = LogEntry(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="test_action",
            message="Test message",
            user_id="user1",
            details={"key": "value"},
            tags=["tag1", "tag2"]
        )
        
        doc = entry.to_mongo_doc()
        
        assert "id" not in doc  # id 应该被排除
        assert doc["log_type"] == LogType.OPERATION
        assert doc["action"] == "test_action"
        assert doc["details"] == {"key": "value"}
        assert "tags" in doc
    
    def test_log_entry_from_mongo_doc(self):
        """测试从 MongoDB 文档创建"""
        doc = {
            "_id": "507f1f77bcf86cd799439011",
            "log_type": "operation",
            "level": "info",
            "action": "test",
            "message": "Test",
            "timestamp": datetime.utcnow()
        }
        
        entry = LogEntry.from_mongo_doc(doc)
        
        assert entry.id == "507f1f77bcf86cd799439011"
        assert entry.log_type == LogType.OPERATION
        assert entry.action == "test"
    
    def test_log_entry_serialization(self):
        """测试序列化"""
        now = datetime.utcnow()
        entry = LogEntry(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="test",
            message="Test",
            timestamp=now
        )
        
        data = entry.model_dump()
        
        assert "log_type" in data
        assert "timestamp" in data
        # datetime 应该被序列化为 ISO 格式字符串
        assert isinstance(data["timestamp"], str)


class TestAuditLogEntry:
    """测试审计日志条目"""
    
    def test_audit_entry_creation(self):
        """测试审计条目创建"""
        entry = AuditLogEntry(
            action="update_config",
            message="修改配置",
            audit_type=AuditLogEntry.AuditType.UPDATE,
            resource_type="config",
            resource_id="setting_1",
            old_value={"enabled": False},
            new_value={"enabled": True},
            compliance_tags=["security"]
        )
        
        assert entry.log_type == LogType.AUDIT
        assert entry.audit_type == AuditLogEntry.AuditType.UPDATE
        assert entry.resource_type == "config"
        assert entry.old_value == {"enabled": False}
        assert entry.new_value == {"enabled": True}
    
    def test_audit_type_constants(self):
        """测试审计类型常量"""
        assert AuditLogEntry.AuditType.LOGIN == "login"
        assert AuditLogEntry.AuditType.LOGOUT == "logout"
        assert AuditLogEntry.AuditType.CREATE == "create"
        assert AuditLogEntry.AuditType.UPDATE == "update"
        assert AuditLogEntry.AuditType.DELETE == "delete"


class TestErrorLogEntry:
    """测试错误日志条目"""
    
    def test_error_entry_creation(self):
        """测试错误条目创建"""
        entry = ErrorLogEntry(
            action="api_call",
            message="API调用失败",
            error_type="ConnectionError",
            error_code="ERR_001",
            stack_trace="Traceback...",
            context={"url": "http://api.example.com"}
        )
        
        assert entry.log_type == LogType.ERROR
        assert entry.level == LogLevel.ERROR
        assert entry.error_type == "ConnectionError"
        assert entry.is_resolved is False
        assert entry.resolved_at is None
    
    def test_error_entry_resolution(self):
        """测试错误解决状态"""
        entry = ErrorLogEntry(
            action="test",
            message="Test error",
            error_type="TestError",
            is_resolved=True,
            resolved_at=datetime.utcnow(),
            resolved_by="admin"
        )
        
        assert entry.is_resolved is True
        assert entry.resolved_by == "admin"


class TestLogStats:
    """测试日志统计模型"""
    
    def test_user_activity_stats(self):
        """测试用户活动统计"""
        stats = UserActivityStats(
            user_id="user1",
            username="User One",
            period_days=30,
            total_actions=100,
            active_days=20,
            action_distribution={"login": 50, "view": 50},
            hourly_distribution=[0] * 24
        )
        
        assert stats.user_id == "user1"
        assert stats.total_actions == 100
        assert stats.active_days == 20
        assert stats.avg_daily_actions == 5.0  # 100 / 20
    
    def test_security_stats(self):
        """测试安全统计"""
        stats = SecurityStats(
            period_hours=24,
            total_threats=10,
            critical_threats=1,
            high_threats=3,
            failed_login_attempts=50
        )
        
        assert stats.total_threats == 10
        assert stats.critical_threats == 1
        assert stats.failed_login_attempts == 50
    
    def test_log_trend(self):
        """测试日志趋势"""
        trend = LogTrend(
            timestamp=datetime.utcnow(),
            count=100,
            error_count=5,
            avg_duration_ms=150.5
        )
        
        assert trend.count == 100
        assert trend.error_count == 5
        assert trend.avg_duration_ms == 150.5
