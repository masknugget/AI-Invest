"""
日志模块测试 Fixtures
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Generator

from app.services.logging.models import (
    LogEntry, LogType, LogLevel,
    AuditLogEntry, ErrorLogEntry, 
    UserActivityStats, SecurityStats
)
from app.services.logging.core import MemoryLogStorage


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def memory_storage():
    """内存存储实例"""
    storage = MemoryLogStorage(max_size=1000)
    yield storage
    storage.clear()


@pytest.fixture
def sample_log_entry():
    """示例日志条目"""
    return {
        "log_type": LogType.OPERATION,
        "level": LogLevel.INFO,
        "action": "user_login",
        "message": "用户登录成功",
        "user_id": "test_user",
        "username": "Test User",
        "timestamp": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "details": {"ip": "127.0.0.1", "browser": "Chrome"}
    }


@pytest.fixture
def sample_error_entry():
    """示例错误日志条目"""
    return {
        "log_type": LogType.ERROR,
        "level": LogLevel.ERROR,
        "action": "api_request",
        "message": "API请求失败",
        "user_id": "test_user",
        "error_type": "TimeoutError",
        "error_code": "ERR_001",
        "stack_trace": "Traceback (most recent call last):...",
        "timestamp": datetime.utcnow(),
        "created_at": datetime.utcnow()
    }


@pytest.fixture
def sample_audit_entry():
    """示例审计日志条目"""
    return {
        "log_type": LogType.AUDIT,
        "level": LogLevel.INFO,
        "audit_type": AuditLogEntry.AuditType.UPDATE,
        "action": "update_config",
        "message": "修改系统配置",
        "user_id": "admin",
        "resource_type": "config",
        "resource_id": "llm_settings",
        "old_value": {"model": "gpt-3"},
        "new_value": {"model": "gpt-4"},
        "compliance_tags": ["security", "config"],
        "timestamp": datetime.utcnow(),
        "created_at": datetime.utcnow()
    }


@pytest.fixture
def multiple_log_entries():
    """多条日志条目"""
    entries = []
    base_time = datetime.utcnow() - timedelta(hours=1)
    
    for i in range(10):
        entries.append({
            "log_type": LogType.OPERATION if i % 2 == 0 else LogType.ACCESS,
            "level": LogLevel.INFO if i < 8 else LogLevel.ERROR,
            "action": f"action_{i}",
            "message": f"Message {i}",
            "user_id": f"user_{i % 3}",
            "timestamp": base_time + timedelta(minutes=i * 5),
            "created_at": base_time + timedelta(minutes=i * 5)
        })
    
    return entries


@pytest.fixture
def mock_user_activity_data():
    """模拟用户活动数据"""
    base_time = datetime.utcnow() - timedelta(days=7)
    logs = []
    
    # 模拟7天的活动
    for day in range(7):
        for hour in [9, 10, 14, 15, 16]:  # 工作时间
            logs.append({
                "log_type": LogType.OPERATION,
                "level": LogLevel.INFO,
                "action": "stock_analysis",
                "message": "分析股票",
                "user_id": "test_user",
                "username": "Test User",
                "timestamp": base_time + timedelta(days=day, hours=hour),
                "details": {"feature": "analysis"},
                "success": True,
                "duration_ms": 100 + day * 10
            })
    
    return logs


@pytest.fixture
def mock_security_data():
    """模拟安全日志数据"""
    base_time = datetime.utcnow() - timedelta(hours=24)
    logs = []
    
    # 正常登录
    for i in range(20):
        logs.append({
            "log_type": LogType.OPERATION,
            "level": LogLevel.INFO,
            "action": "user_login",
            "message": "用户登录",
            "user_id": f"user_{i % 5}",
            "ip_address": f"192.168.1.{i % 10}",
            "timestamp": base_time + timedelta(hours=i),
            "success": True
        })
    
    # 暴力破解攻击
    for i in range(10):
        logs.append({
            "log_type": LogType.SECURITY,
            "level": LogLevel.WARNING,
            "action": "user_login",
            "message": "登录失败",
            "user_id": "victim_user",
            "ip_address": "10.0.0.1",
            "timestamp": base_time + timedelta(minutes=i * 2),
            "success": False
        })
    
    return logs


class AsyncMock:
    """异步 Mock 对象"""
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.call_args = None
        self.call_count = 0
    
    async def __call__(self, *args, **kwargs):
        self.call_args = (args, kwargs)
        self.call_count += 1
        return self.return_value
