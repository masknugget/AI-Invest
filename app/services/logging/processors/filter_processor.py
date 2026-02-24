"""
日志过滤处理器
"""

import re
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
import logging

from app.services.logging.models import LogLevel, LogType

logger = logging.getLogger("webapi")


@dataclass
class LogFilterRule:
    """日志过滤规则"""
    name: str
    enabled: bool = True
    
    # 匹配条件
    log_types: Optional[List[str]] = None
    levels: Optional[List[str]] = None
    users: Optional[List[str]] = None
    actions: Optional[List[str]] = None
    contains_text: Optional[str] = None
    regex_pattern: Optional[str] = None
    
    # 字段匹配
    field_conditions: Optional[Dict[str, Any]] = None
    
    # 行为
    action: str = "keep"  # keep/drop/tag/sample
    sample_rate: float = 1.0
    tags_to_add: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.regex_pattern:
            self._compiled_regex = re.compile(self.regex_pattern)
        else:
            self._compiled_regex = None
    
    def matches(self, log_entry: Dict[str, Any]) -> bool:
        """检查日志是否匹配规则"""
        if not self.enabled:
            return False
        
        # 类型匹配
        if self.log_types is not None:
            if log_entry.get("log_type") not in self.log_types:
                return False
        
        # 级别匹配
        if self.levels is not None:
            if log_entry.get("level") not in self.levels:
                return False
        
        # 用户匹配
        if self.users is not None:
            if log_entry.get("user_id") not in self.users:
                return False
        
        # 动作匹配
        if self.actions is not None:
            if log_entry.get("action") not in self.actions:
                return False
        
        # 文本匹配
        if self.contains_text is not None:
            message = log_entry.get("message", "")
            if self.contains_text not in message:
                return False
        
        # 正则匹配
        if self._compiled_regex is not None:
            message = log_entry.get("message", "")
            if not self._compiled_regex.search(message):
                return False
        
        # 字段条件匹配
        if self.field_conditions is not None:
            for field, expected_value in self.field_conditions.items():
                actual_value = self._get_nested_value(log_entry, field)
                if actual_value != expected_value:
                    return False
        
        return True
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


class FilterProcessor:
    """日志过滤处理器"""
    
    def __init__(self):
        self.rules: List[LogFilterRule] = []
        self._default_action = "keep"
        self._stats = {
            "total_processed": 0,
            "matched": {},
            "dropped": 0,
            "tagged": 0,
            "sampled": 0
        }
    
    def add_rule(self, rule: LogFilterRule) -> "FilterProcessor":
        """添加过滤规则"""
        self.rules.append(rule)
        self._stats["matched"][rule.name] = 0
        return self
    
    def remove_rule(self, name: str) -> bool:
        """移除过滤规则"""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                self._stats["matched"].pop(name, None)
                return True
        return False
    
    async def process(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理日志条目
        
        Returns:
            处理后的日志，None 表示丢弃
        """
        self._stats["total_processed"] += 1
        
        for rule in self.rules:
            if rule.matches(log_entry):
                self._stats["matched"][rule.name] = self._stats["matched"].get(rule.name, 0) + 1
                
                if rule.action == "drop":
                    self._stats["dropped"] += 1
                    return None
                
                elif rule.action == "tag":
                    if rule.tags_to_add:
                        tags = log_entry.get("tags", [])
                        log_entry["tags"] = list(set(tags + rule.tags_to_add))
                    self._stats["tagged"] += 1
                
                elif rule.action == "sample":
                    import random
                    if random.random() > rule.sample_rate:
                        self._stats["sampled"] += 1
                        return None
                    log_entry["_sampled_by_rule"] = rule.name
                    log_entry["_sample_rate"] = rule.sample_rate
        
        return log_entry
    
    def get_stats(self) -> Dict[str, Any]:
        """获取过滤统计"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        self._stats["total_processed"] = 0
        self._stats["matched"] = {name: 0 for name in self._stats["matched"]}
        self._stats["dropped"] = 0
        self._stats["tagged"] = 0
        self._stats["sampled"] = 0


class DynamicFilter:
    """动态过滤器 - 可根据运行时条件调整"""
    
    def __init__(self):
        self._min_level = LogLevel.DEBUG
        self._excluded_users: set = set()
        self._excluded_actions: set = set()
        self._excluded_patterns: List[re.Pattern] = []
        self._rate_limits: Dict[str, Dict] = {}  # 按动作类型限流
    
    def set_min_level(self, level: LogLevel):
        """设置最小日志级别"""
        self._min_level = level
    
    def exclude_user(self, user_id: str):
        """排除特定用户"""
        self._excluded_users.add(user_id)
    
    def include_user(self, user_id: str):
        """包含特定用户"""
        self._excluded_users.discard(user_id)
    
    def exclude_action(self, action: str):
        """排除特定动作"""
        self._excluded_actions.add(action)
    
    def add_exclude_pattern(self, pattern: str):
        """添加排除正则"""
        self._excluded_patterns.append(re.compile(pattern))
    
    def set_rate_limit(self, action: str, max_logs: int, window_seconds: int):
        """设置动作级别的速率限制"""
        import time
        self._rate_limits[action] = {
            "max_logs": max_logs,
            "window_seconds": window_seconds,
            "logs": [],
            "last_reset": time.time()
        }
    
    def should_filter(self, log_entry: Dict[str, Any]) -> bool:
        """判断是否应该过滤该日志"""
        # 级别检查
        level_priority = {
            LogLevel.DEBUG: 0, LogLevel.INFO: 1,
            LogLevel.WARNING: 2, LogLevel.ERROR: 3, LogLevel.CRITICAL: 4
        }
        entry_level = level_priority.get(log_entry.get("level"), 0)
        min_level = level_priority.get(self._min_level, 0)
        if entry_level < min_level:
            return True
        
        # 用户检查
        if log_entry.get("user_id") in self._excluded_users:
            return True
        
        # 动作检查
        if log_entry.get("action") in self._excluded_actions:
            return True
        
        # 正则检查
        message = log_entry.get("message", "")
        for pattern in self._excluded_patterns:
            if pattern.search(message):
                return True
        
        # 速率限制检查
        action = log_entry.get("action")
        if action in self._rate_limits:
            if self._check_rate_limit(action):
                return True
        
        return False
    
    def _check_rate_limit(self, action: str) -> bool:
        """检查是否触发速率限制"""
        import time
        
        limit = self._rate_limits[action]
        now = time.time()
        
        # 重置窗口
        if now - limit["last_reset"] > limit["window_seconds"]:
            limit["logs"] = []
            limit["last_reset"] = now
        
        # 检查限制
        if len(limit["logs"]) >= limit["max_logs"]:
            return True
        
        limit["logs"].append(now)
        return False


# 预定义的过滤规则
PREDEFINED_RULES = {
    "ignore_health_checks": LogFilterRule(
        name="ignore_health_checks",
        actions=["/health", "/healthz", "/readyz"],
        action="drop"
    ),
    "sample_debug_logs": LogFilterRule(
        name="sample_debug_logs",
        levels=["debug"],
        action="sample",
        sample_rate=0.1
    ),
    "tag_security_events": LogFilterRule(
        name="tag_security_events",
        log_types=["security"],
        action="tag",
        tags_to_add=["high_priority", "alert"]
    ),
    "drop_test_user_logs": LogFilterRule(
        name="drop_test_user_logs",
        users=["test", "demo", "guest"],
        action="drop"
    )
}
