"""
基础日志处理器
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
import logging

logger = logging.getLogger("webapi")


class LogProcessor(ABC):
    """日志处理器抽象基类"""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.enabled = True
        self._next: Optional[LogProcessor] = None
    
    @abstractmethod
    async def process(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理日志条目
        
        Args:
            log_entry: 日志条目
            
        Returns:
            处理后的日志条目，None 表示丢弃
        """
        pass
    
    def set_next(self, processor: "LogProcessor") -> "LogProcessor":
        """设置下一个处理器（责任链模式）"""
        self._next = processor
        return processor
    
    async def process_next(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """传递给下一个处理器"""
        if self._next and self._next.enabled:
            return await self._next.process(log_entry)
        return log_entry
    
    async def process_chain(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理并传递给链中的下一个"""
        if not self.enabled:
            return await self.process_next(log_entry)
        
        result = await self.process(log_entry)
        if result is None:
            return None
        
        return await self.process_next(result)


class ProcessorChain:
    """处理器链管理"""
    
    def __init__(self):
        self._processors: List[LogProcessor] = []
        self._head: Optional[LogProcessor] = None
    
    def add(self, processor: LogProcessor) -> "ProcessorChain":
        """添加处理器到链尾"""
        if not self._head:
            self._head = processor
        else:
            current = self._head
            while current._next:
                current = current._next
            current.set_next(processor)
        
        self._processors.append(processor)
        return self
    
    async def process(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理日志条目"""
        if not self._head:
            return log_entry
        return await self._head.process_chain(log_entry)
    
    def get_processors(self) -> List[LogProcessor]:
        """获取所有处理器"""
        return self._processors.copy()


class EnrichmentProcessor(LogProcessor):
    """日志增强处理器 - 添加额外上下文"""
    
    def __init__(
        self,
        add_hostname: bool = True,
        add_environment: bool = True,
        custom_fields: Optional[Dict[str, Any]] = None
    ):
        super().__init__("EnrichmentProcessor")
        self.add_hostname = add_hostname
        self.add_environment = add_environment
        self.custom_fields = custom_fields or {}
        self._hostname = None
        self._environment = None
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """添加环境信息"""
        import socket
        
        if self.add_hostname and "hostname" not in log_entry:
            if self._hostname is None:
                self._hostname = socket.gethostname()
            log_entry["hostname"] = self._hostname
        
        if self.add_environment and "environment" not in log_entry:
            if self._environment is None:
                from app.core.config import settings
                self._environment = getattr(settings, "ENVIRONMENT", "development")
            log_entry["environment"] = self._environment
        
        # 添加自定义字段
        log_entry.update(self.custom_fields)
        
        return await self.process_next(log_entry)


class MaskingProcessor(LogProcessor):
    """敏感信息脱敏处理器"""
    
    def __init__(
        self,
        sensitive_fields: Optional[List[str]] = None,
        mask_pattern: str = "***"
    ):
        super().__init__("MaskingProcessor")
        self.sensitive_fields = sensitive_fields or [
            "password", "token", "secret", "api_key",
            "credit_card", "ssn", "phone", "email"
        ]
        self.mask_pattern = mask_pattern
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏处理"""
        if "details" in log_entry:
            log_entry["details"] = self._mask_dict(log_entry["details"])
        
        if "message" in log_entry and isinstance(log_entry["message"], str):
            log_entry["message"] = self._mask_string(log_entry["message"])
        
        return await self.process_next(log_entry)
    
    def _mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """递归脱敏字典"""
        result = {}
        for key, value in data.items():
            lower_key = key.lower()
            
            # 检查是否是敏感字段
            if any(s in lower_key for s in self.sensitive_fields):
                result[key] = self.mask_pattern
            elif isinstance(value, dict):
                result[key] = self._mask_dict(value)
            elif isinstance(value, list):
                result[key] = [self._mask_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        
        return result
    
    def _mask_string(self, text: str) -> str:
        """脱敏字符串中的敏感信息"""
        import re
        
        # 邮箱脱敏
        text = re.sub(
            r'[\w\.-]+@[\w\.-]+\.\w+',
            self.mask_pattern,
            text
        )
        
        # 手机号脱敏（中国大陆）
        text = re.sub(
            r'1[3-9]\d{9}',
            self.mask_pattern,
            text
        )
        
        return text


class SamplingProcessor(LogProcessor):
    """日志采样处理器 - 减少日志量"""
    
    def __init__(
        self,
        sample_rate: float = 1.0,
        min_level_for_full: str = "error"
    ):
        super().__init__("SamplingProcessor")
        self.sample_rate = max(0.0, min(1.0, sample_rate))
        self.min_level_for_full = min_level_for_full
        self._counter = 0
    
    async def process(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """采样处理"""
        # 高优先级日志全量保留
        level = log_entry.get("level", "info")
        if self._should_keep_full(level):
            return await self.process_next(log_entry)
        
        # 采样
        self._counter += 1
        if self._counter % int(1 / self.sample_rate) == 0:
            log_entry["_sampled"] = True
            log_entry["_sample_rate"] = self.sample_rate
            return await self.process_next(log_entry)
        
        return None  # 丢弃
    
    def _should_keep_full(self, level: str) -> bool:
        """判断是否全量保留"""
        level_priority = {
            "debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4
        }
        return level_priority.get(level, 0) >= level_priority.get(self.min_level_for_full, 3)


class ThrottlingProcessor(LogProcessor):
    """日志限流处理器 - 防止日志洪峰"""
    
    def __init__(
        self,
        max_logs_per_second: int = 1000,
        burst_size: int = 100
    ):
        super().__init__("ThrottlingProcessor")
        self.max_logs_per_second = max_logs_per_second
        self.burst_size = burst_size
        self._tokens = burst_size
        self._last_update = 0
    
    async def process(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """限流处理"""
        import time
        
        now = time.time()
        
        # 补充令牌
        time_passed = now - self._last_update
        self._tokens = min(
            self.burst_size,
            self._tokens + time_passed * self.max_logs_per_second
        )
        self._last_update = now
        
        # 消费令牌
        if self._tokens >= 1:
            self._tokens -= 1
            return await self.process_next(log_entry)
        
        # 限流丢弃或降级
        level = log_entry.get("level", "info")
        if level in ["error", "critical"]:
            log_entry["_throttled"] = True
            return await self.process_next(log_entry)
        
        return None


class MetricsProcessor(LogProcessor):
    """指标收集处理器"""
    
    def __init__(self, metrics_callback: Optional[Callable] = None):
        super().__init__("MetricsProcessor")
        self.metrics_callback = metrics_callback
        self._counters: Dict[str, int] = {}
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """收集指标"""
        log_type = log_entry.get("log_type", "unknown")
        level = log_entry.get("level", "info")
        
        # 更新计数器
        self._counters[f"{log_type}:{level}"] = self._counters.get(f"{log_type}:{level}", 0) + 1
        
        # 回调通知
        if self.metrics_callback:
            try:
                self.metrics_callback(log_entry)
            except Exception as e:
                logger.debug(f"Metrics callback error: {e}")
        
        return await self.process_next(log_entry)
    
    def get_counters(self) -> Dict[str, int]:
        """获取计数器"""
        return self._counters.copy()
    
    def reset_counters(self):
        """重置计数器"""
        self._counters.clear()
