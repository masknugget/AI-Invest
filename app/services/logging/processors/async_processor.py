"""
异步批量日志处理器
高性能日志写入
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Callable
from collections import deque
from dataclasses import dataclass, field
import logging

from app.services.logging.models import LogLevel

logger = logging.getLogger("webapi")


@dataclass
class LogQueue:
    """日志队列配置"""
    max_size: int = 10000
    high_watermark: float = 0.8
    low_watermark: float = 0.3
    drop_policy: str = "oldest"  # oldest/newest/low_priority
    
    def is_full(self, current_size: int) -> bool:
        return current_size >= self.max_size
    
    def is_high_watermark(self, current_size: int) -> bool:
        return current_size >= self.max_size * self.high_watermark
    
    def is_low_watermark(self, current_size: int) -> bool:
        return current_size <= self.max_size * self.low_watermark


class AsyncBatchProcessor:
    """异步批量日志处理器"""
    
    def __init__(
        self,
        storage,
        queue_config: Optional[LogQueue] = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_threshold: int = 5
    ):
        self.storage = storage
        self.queue_config = queue_config or LogQueue()
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.circuit_breaker_threshold = circuit_breaker_threshold
        
        # 队列
        self._queue: deque = deque()
        self._lock = asyncio.Lock()
        self._flush_event = asyncio.Event()
        
        # 任务
        self._flush_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 统计
        self._stats = {
            "enqueued": 0,
            "dropped": 0,
            "flushed": 0,
            "failed": 0,
            "retried": 0,
            "last_flush_time": 0,
            "queue_high_watermark_hits": 0
        }
        
        # 熔断器
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_time: Optional[float] = None
        
        # 回调
        self._on_flush: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._on_drop: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_flush: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_drop: Optional[Callable] = None
    ):
        """设置回调函数"""
        self._on_flush = on_flush
        self._on_error = on_error
        self._on_drop = on_drop
    
    async def start(self):
        """启动处理器"""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"AsyncBatchProcessor started (batch_size={self.batch_size}, flush_interval={self.flush_interval}s)")
    
    async def stop(self, flush_remaining: bool = True):
        """停止处理器"""
        self._running = False
        self._flush_event.set()  # 唤醒刷新循环
        
        # 取消任务
        for task in [self._flush_task, self._monitor_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 刷新剩余日志
        if flush_remaining:
            await self._flush(force=True)
        
        logger.info(f"AsyncBatchProcessor stopped. Stats: {self._stats}")
    
    async def enqueue(self, entry: Dict[str, Any]) -> bool:
        """
        入队日志条目
        
        Returns:
            True: 成功入队
            False: 队列已满，丢弃
        """
        # 熔断检查
        if self._circuit_open:
            if time.time() - (self._circuit_open_time or 0) > 30:  # 30秒后尝试恢复
                self._circuit_open = False
                self._failure_count = 0
                logger.info("Circuit breaker closed, resuming log processing")
            else:
                self._stats["dropped"] += 1
                return False
        
        async with self._lock:
            # 检查队列容量
            if self.queue_config.is_full(len(self._queue)):
                self._stats["dropped"] += 1
                
                # 根据策略处理
                if self.queue_config.drop_policy == "oldest":
                    self._queue.popleft()
                    self._queue.append(entry)
                    if self._on_drop:
                        asyncio.create_task(self._on_drop(entry, "queue_full_oldest_dropped"))
                elif self.queue_config.drop_policy == "newest":
                    if self._on_drop:
                        asyncio.create_task(self._on_drop(entry, "queue_full_newest_dropped"))
                    return False
                else:  # low_priority
                    # 尝试丢弃低优先级日志
                    dropped = self._drop_low_priority()
                    if dropped:
                        self._queue.append(entry)
                    else:
                        return False
            else:
                self._queue.append(entry)
            
            self._stats["enqueued"] += 1
            
            # 高水位检查
            if self.queue_config.is_high_watermark(len(self._queue)):
                self._stats["queue_high_watermark_hits"] += 1
                self._flush_event.set()  # 触发刷新
        
        return True
    
    def _drop_low_priority(self) -> bool:
        """丢弃低优先级日志，返回是否成功"""
        priority_order = ["debug", "info", "warning", "error", "critical"]
        
        for level in priority_order:
            for i, entry in enumerate(self._queue):
                if entry.get("level") == level:
                    dropped = self._queue[i]
                    del self._queue[i]
                    if self._on_drop:
                        asyncio.create_task(self._on_drop(dropped, "low_priority_dropped"))
                    return True
        
        return False
    
    async def _flush_loop(self):
        """定时刷新循环"""
        while self._running:
            try:
                # 等待刷新信号或超时
                try:
                    await asyncio.wait_for(
                        self._flush_event.wait(),
                        timeout=self.flush_interval
                    )
                except asyncio.TimeoutError:
                    pass
                
                self._flush_event.clear()
                
                # 执行刷新
                if self._queue:
                    await self._flush()
                    
            except Exception as e:
                logger.error(f"Flush loop error: {e}")
                await asyncio.sleep(1)
    
    async def _flush(self, force: bool = False):
        """刷新队列到存储"""
        async with self._lock:
            if not self._queue:
                return
            
            # 批量获取
            batch = []
            while self._queue and len(batch) < self.batch_size:
                batch.append(self._queue.popleft())
        
        if not batch:
            return
        
        # 重试写入
        success = False
        for attempt in range(self.retry_attempts):
            try:
                await self.storage.write_batch(batch)
                success = True
                self._stats["flushed"] += len(batch)
                self._stats["last_flush_time"] = time.time()
                
                # 重置熔断器
                if self._failure_count > 0:
                    self._failure_count = 0
                
                # 回调
                if self._on_flush:
                    asyncio.create_task(self._on_flush(batch))
                
                break
                
            except Exception as e:
                self._stats["failed"] += 1
                self._failure_count += 1
                
                logger.warning(f"Flush attempt {attempt + 1} failed: {e}")
                
                if attempt < self.retry_attempts - 1:
                    self._stats["retried"] += 1
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    # 所有重试失败
                    logger.error(f"Failed to flush {len(batch)} logs after {self.retry_attempts} attempts")
                    
                    # 触发熔断
                    if self._failure_count >= self.circuit_breaker_threshold:
                        self._circuit_open = True
                        self._circuit_open_time = time.time()
                        logger.error("Circuit breaker opened due to persistent failures")
                    
                    # 回调
                    if self._on_error:
                        asyncio.create_task(self._on_error(batch, e))
                    
                    # 重新入队（可选，这里选择丢弃以避免无限循环）
                    # 对于重要日志可以改为重新入队
        
        # 如果队列仍然有大量数据，立即再次刷新
        async with self._lock:
            if force or (self._queue and len(self._queue) >= self.batch_size):
                self._flush_event.set()
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟报告一次
                
                async with self._lock:
                    queue_size = len(self._queue)
                
                logger.debug(
                    f"Log processor stats: enqueued={self._stats['enqueued']}, "
                    f"flushed={self._stats['flushed']}, dropped={self._stats['dropped']}, "
                    f"queue_size={queue_size}, circuit_open={self._circuit_open}"
                )
                
            except Exception as e:
                logger.debug(f"Monitor loop error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "circuit_open": self._circuit_open,
            "failure_count": self._failure_count
        }
    
    def reset_stats(self):
        """重置统计"""
        for key in self._stats:
            if isinstance(self._stats[key], int):
                self._stats[key] = 0


class PriorityAsyncProcessor(AsyncBatchProcessor):
    """优先级异步处理器"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 使用多个队列按优先级分离
        self._priority_queues: Dict[str, deque] = {
            "critical": deque(),
            "error": deque(),
            "warning": deque(),
            "info": deque(),
            "debug": deque()
        }
        self._priority_weights = {
            "critical": 10,
            "error": 5,
            "warning": 2,
            "info": 1,
            "debug": 0.5
        }
    
    async def enqueue(self, entry: Dict[str, Any]) -> bool:
        """按优先级入队"""
        level = entry.get("level", "info")
        queue = self._priority_queues.get(level, self._priority_queues["info"])
        
        if len(queue) >= self.queue_config.max_size // 5:  # 每个优先级队列容量
            self._stats["dropped"] += 1
            return False
        
        queue.append(entry)
        self._stats["enqueued"] += 1
        
        # 高优先级立即触发刷新
        if level in ["critical", "error"]:
            self._flush_event.set()
        
        return True
    
    async def _flush(self, force: bool = False):
        """按优先级刷新"""
        batch = []
        
        # 按优先级顺序取数据
        for level in ["critical", "error", "warning", "info", "debug"]:
            queue = self._priority_queues[level]
            weight = self._priority_weights[level]
            target_count = int(self.batch_size * weight / sum(self._priority_weights.values()))
            target_count = max(1, target_count)
            
            while queue and len(batch) < self.batch_size and len(batch) < target_count:
                batch.append(queue.popleft())
            
            if len(batch) >= self.batch_size:
                break
        
        if batch:
            await self._write_batch_with_retry(batch)
    
    async def _write_batch_with_retry(self, batch: List[Dict[str, Any]]):
        """带重试的批量写入"""
        for attempt in range(self.retry_attempts):
            try:
                await self.storage.write_batch(batch)
                self._stats["flushed"] += len(batch)
                return
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.retry_delay * (attempt + 1))
