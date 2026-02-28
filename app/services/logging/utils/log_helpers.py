"""
日志工具函数
"""

import uuid
import inspect
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime


def generate_log_id() -> str:
    """生成唯一的日志ID"""
    return str(uuid.uuid4())


def format_log_message(
    template: str,
    **kwargs
) -> str:
    """格式化日志消息，安全处理缺失参数"""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # 如果参数缺失，使用默认值
        return template + f" [missing param: {e}]"
    except Exception as e:
        return f"{template} [format error: {e}]"


def truncate_log_message(
    message: str,
    max_length: int = 1000,
    suffix: str = "..."
) -> str:
    """截断过长的日志消息"""
    if len(message) <= max_length:
        return message
    return message[:max_length - len(suffix)] + suffix


def sanitize_log_data(
    data: Dict[str, Any],
    sensitive_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    清理敏感数据
    
    Args:
        data: 原始数据
        sensitive_fields: 敏感字段列表
        
    Returns:
        清理后的数据副本
    """
    if sensitive_fields is None:
        sensitive_fields = [
            "password", "token", "secret", "api_key", "auth",
            "credit_card", "cvv", "ssn", "phone", "email"
        ]
    
    result = {}
    for key, value in data.items():
        lower_key = key.lower()
        
        # 检查是否是敏感字段
        is_sensitive = any(s in lower_key for s in sensitive_fields)
        
        if is_sensitive:
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = sanitize_log_data(value, sensitive_fields)
        elif isinstance(value, list):
            result[key] = [
                sanitize_log_data(item, sensitive_fields) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def get_caller_info(skip_frames: int = 2) -> Dict[str, Any]:
    """获取调用者信息"""
    try:
        frame = inspect.currentframe()
        for _ in range(skip_frames):
            if frame.f_back:
                frame = frame.f_back
            else:
                break
        
        return {
            "filename": frame.f_code.co_filename,
            "function": frame.f_code.co_name,
            "line_no": frame.f_lineno,
            "module": inspect.getmodule(frame).__name__ if inspect.getmodule(frame) else "unknown"
        }
    except Exception:
        return {
            "filename": "unknown",
            "function": "unknown",
            "line_no": 0,
            "module": "unknown"
        }


def build_log_entry(
    log_type: str,
    level: str,
    action: str,
    message: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    **extra_fields
) -> Dict[str, Any]:
    """
    构建标准日志条目
    
    Args:
        log_type: 日志类型
        level: 日志级别
        action: 动作
        message: 消息
        user_id: 用户ID
        username: 用户名
        **extra_fields: 额外字段
        
    Returns:
        日志条目字典
    """
    entry = {
        "log_type": log_type,
        "level": level,
        "action": action,
        "message": message,
        "timestamp": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    }
    
    if user_id:
        entry["user_id"] = user_id
    if username:
        entry["username"] = username
    
    # 添加额外字段
    entry.update(extra_fields)
    
    return entry


def format_stack_trace(exception: Exception, limit: int = 10) -> str:
    """格式化异常堆栈"""
    return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__, limit=limit))


def extract_error_code(exception: Exception) -> Optional[str]:
    """提取错误代码"""
    if hasattr(exception, 'code'):
        return str(exception.code)
    if hasattr(exception, 'error_code'):
        return str(exception.error_code)
    return None


def calculate_log_hash(log_entry: Dict[str, Any]) -> str:
    """计算日志指纹（用于去重）"""
    import hashlib
    
    # 选取关键字段计算哈希
    key_fields = [
        log_entry.get("log_type"),
        log_entry.get("level"),
        log_entry.get("action"),
        log_entry.get("error_type"),
        log_entry.get("user_id")
    ]
    
    content = "|".join(str(f) for f in key_fields if f)
    return hashlib.md5(content.encode()).hexdigest()[:8]


def is_duplicate_log(
    log_entry: Dict[str, Any],
    recent_logs: List[Dict[str, Any]],
    time_window_seconds: int = 60
) -> bool:
    """检查是否是重复日志"""
    current_hash = calculate_log_hash(log_entry)
    current_time = log_entry.get("timestamp", datetime.utcnow())
    
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    
    for recent in recent_logs:
        if calculate_log_hash(recent) != current_hash:
            continue
        
        recent_time = recent.get("timestamp")
        if isinstance(recent_time, str):
            recent_time = datetime.fromisoformat(recent_time)
        
        if recent_time and (current_time - recent_time).total_seconds() < time_window_seconds:
            return True
    
    return False
