"""
日志工具函数测试
"""

import pytest
from datetime import datetime

from app.services.logging.utils import (
    generate_log_id,
    format_log_message,
    truncate_log_message,
    sanitize_log_data,
    get_caller_info,
    build_log_entry,
    format_stack_trace,
    extract_error_code,
    calculate_log_hash,
    is_duplicate_log
)


class TestLogHelpers:
    """测试日志工具函数"""
    
    def test_generate_log_id(self):
        """测试生成日志ID"""
        id1 = generate_log_id()
        id2 = generate_log_id()
        
        assert id1 is not None
        assert id2 is not None
        assert id1 != id2  # 应该是唯一的
        assert len(id1) == 36  # UUID 格式
    
    def test_format_log_message_success(self):
        """测试成功格式化日志消息"""
        template = "User {user} performed {action}"
        result = format_log_message(template, user="admin", action="login")
        
        assert result == "User admin performed login"
    
    def test_format_log_message_missing_param(self):
        """测试格式化时缺少参数"""
        template = "User {user} performed {action}"
        result = format_log_message(template, user="admin")
        
        assert "missing param" in result
        assert "User admin performed" in result
    
    def test_truncate_log_message_short(self):
        """测试短消息不截断"""
        message = "Short message"
        result = truncate_log_message(message, max_length=100)
        
        assert result == message
    
    def test_truncate_log_message_long(self):
        """测试长消息截断"""
        message = "A" * 2000
        result = truncate_log_message(message, max_length=100)
        
        assert len(result) == 100
        assert result.endswith("...")
    
    def test_truncate_custom_suffix(self):
        """测试自定义截断后缀"""
        message = "A" * 200
        result = truncate_log_message(message, max_length=100, suffix="[more]")
        
        assert result.endswith("[more]")
    
    def test_sanitize_log_data_basic(self):
        """测试基础数据脱敏"""
        data = {
            "username": "admin",
            "password": "secret123",
            "email": "test@example.com"
        }
        
        result = sanitize_log_data(data)
        
        assert result["username"] == "admin"
        assert result["password"] == "***REDACTED***"
        assert result["email"] == "***REDACTED***"
    
    def test_sanitize_log_data_nested(self):
        """测试嵌套数据脱敏"""
        data = {
            "user": {
                "name": "admin",
                "api_key": "secret_key"
            },
            "config": {
                "token": "bearer_token"
            }
        }
        
        result = sanitize_log_data(data)
        
        assert result["user"]["name"] == "admin"
        assert result["user"]["api_key"] == "***REDACTED***"
        assert result["config"]["token"] == "***REDACTED***"
    
    def test_sanitize_log_data_list(self):
        """测试列表数据脱敏"""
        data = {
            "users": [
                {"name": "user1", "password": "pass1"},
                {"name": "user2", "password": "pass2"}
            ]
        }
        
        result = sanitize_log_data(data)
        
        assert result["users"][0]["password"] == "***REDACTED***"
        assert result["users"][1]["password"] == "***REDACTED***"
    
    def test_sanitize_custom_fields(self):
        """测试自定义敏感字段"""
        data = {
            "secret_key": "value1",
            "normal": "value2",
            "custom_sensitive": "value3"
        }
        
        result = sanitize_log_data(data, sensitive_fields=["secret", "custom"])
        
        assert result["secret_key"] == "***REDACTED***"
        assert result["normal"] == "value2"
        assert result["custom_sensitive"] == "***REDACTED***"
    
    def test_get_caller_info(self):
        """测试获取调用者信息"""
        info = get_caller_info()
        
        assert "filename" in info
        assert "function" in info
        assert "line_no" in info
        assert "module" in info
    
    def test_build_log_entry(self):
        """测试构建日志条目"""
        entry = build_log_entry(
            log_type="operation",
            level="info",
            action="login",
            message="User logged in",
            user_id="admin",
            username="Administrator",
            extra_field="extra_value"
        )
        
        assert entry["log_type"] == "operation"
        assert entry["level"] == "info"
        assert entry["action"] == "login"
        assert entry["user_id"] == "admin"
        assert entry["username"] == "Administrator"
        assert entry["extra_field"] == "extra_value"
        assert isinstance(entry["timestamp"], datetime)
    
    def test_build_log_entry_optional_fields(self):
        """测试构建可选字段的日志条目"""
        entry = build_log_entry(
            log_type="system",
            level="error",
            action="error",
            message="Error occurred"
        )
        
        assert "user_id" not in entry
        assert "username" not in entry
    
    def test_format_stack_trace(self):
        """测试格式化堆栈跟踪"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            trace = format_stack_trace(e, limit=5)
        
        assert "ValueError" in trace
        assert "Test error" in trace
    
    def test_extract_error_code_with_code(self):
        """测试提取带 code 的错误代码"""
        class CustomError(Exception):
            code = "ERR_001"
        
        try:
            raise CustomError("Error")
        except Exception as e:
            code = extract_error_code(e)
        
        assert code == "ERR_001"
    
    def test_extract_error_code_without_code(self):
        """测试提取不带 code 的错误代码"""
        try:
            raise ValueError("Error")
        except Exception as e:
            code = extract_error_code(e)
        
        assert code is None
    
    def test_calculate_log_hash(self):
        """测试计算日志哈希"""
        entry1 = {
            "log_type": "operation",
            "level": "info",
            "action": "login",
            "user_id": "admin"
        }
        
        entry2 = {
            "log_type": "operation",
            "level": "info",
            "action": "login",
            "user_id": "admin"
        }
        
        entry3 = {
            "log_type": "error",
            "level": "error",
            "action": "login",
            "user_id": "admin"
        }
        
        hash1 = calculate_log_hash(entry1)
        hash2 = calculate_log_hash(entry2)
        hash3 = calculate_log_hash(entry3)
        
        assert hash1 == hash2  # 相同内容应该产生相同哈希
        assert hash1 != hash3  # 不同内容应该产生不同哈希
        assert len(hash1) == 8  # 哈希长度
    
    def test_is_duplicate_log_true(self):
        """测试重复日志检测 - 重复"""
        now = datetime.utcnow()
        
        entry = {
            "log_type": "error",
            "level": "error",
            "action": "api_error",
            "timestamp": now
        }
        
        recent_logs = [
            {
                "log_type": "error",
                "level": "error",
                "action": "api_error",
                "timestamp": now - timedelta(seconds=30)
            }
        ]
        
        result = is_duplicate_log(entry, recent_logs, time_window_seconds=60)
        
        assert result is True
    
    def test_is_duplicate_log_false_different_type(self):
        """测试重复日志检测 - 不同类型"""
        now = datetime.utcnow()
        
        entry = {
            "log_type": "error",
            "level": "error",
            "action": "api_error",
            "timestamp": now
        }
        
        recent_logs = [
            {
                "log_type": "info",
                "level": "info",
                "action": "api_error",
                "timestamp": now - timedelta(seconds=30)
            }
        ]
        
        result = is_duplicate_log(entry, recent_logs, time_window_seconds=60)
        
        assert result is False
    
    def test_is_duplicate_log_false_timeout(self):
        """测试重复日志检测 - 超出时间窗口"""
        now = datetime.utcnow()
        
        entry = {
            "log_type": "error",
            "level": "error",
            "action": "api_error",
            "timestamp": now
        }
        
        recent_logs = [
            {
                "log_type": "error",
                "level": "error",
                "action": "api_error",
                "timestamp": now - timedelta(seconds=120)
            }
        ]
        
        result = is_duplicate_log(entry, recent_logs, time_window_seconds=60)
        
        assert result is False
