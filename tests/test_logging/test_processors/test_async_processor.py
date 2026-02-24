"""
异步批量处理器测试
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from app.services.logging.processors import AsyncBatchProcessor, LogQueue
from app.services.logging.models import LogLevel


class TestLogQueue:
    """测试日志队列配置"""
    
    def test_queue_limits(self):
        """测试队列限制判断"""
        queue = LogQueue(max_size=100)
        
        assert queue.is_full(100) is True
        assert queue.is_full(99) is False
        
        assert queue.is_high_watermark(80) is True
        assert queue.is_high_watermark(79) is False
        
        assert queue.is_low_watermark(30) is True
        assert queue.is_low_watermark(31) is False


class TestAsyncBatchProcessor:
    """测试异步批量处理器"""
    
    @pytest.fixture
    def mock_storage(self):
        """模拟存储"""
        storage = Mock()
        storage.write_batch = AsyncMock(return_value=None)
        return storage
    
    @pytest.fixture
    def processor(self, mock_storage):
        """处理器实例"""
        return AsyncBatchProcessor(
            storage=mock_storage,
            batch_size=5,
            flush_interval=1.0,
            retry_attempts=2,
            retry_delay=0.1
        )
    
    @pytest.mark.asyncio
    async def test_enqueue_success(self, processor):
        """测试成功入队"""
        await processor.start()
        
        entry = {"test": "data"}
        result = await processor.enqueue(entry)
        
        assert result is True
        assert processor._stats["enqueued"] == 1
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_enqueue_queue_full(self, processor):
        """测试队列满时入队"""
        processor.queue_config.max_size = 5
        
        # 填满队列
        for i in range(5):
            await processor.enqueue({"id": i})
        
        # 再次入队应失败
        result = await processor.enqueue({"id": 999})
        
        assert result is False
        assert processor._stats["dropped"] == 1
    
    @pytest.mark.asyncio
    async def test_batch_flush(self, mock_storage, processor):
        """测试批量刷新"""
        await processor.start()
        
        # 快速入队超过批量大小的数据
        for i in range(7):
            await processor.enqueue({"id": i})
        
        # 等待刷新
        await asyncio.sleep(0.2)
        
        await processor.stop()
        
        # 验证批量写入被调用
        assert mock_storage.write_batch.called
    
    @pytest.mark.asyncio
    async def test_periodic_flush(self, mock_storage, processor):
        """测试定时刷新"""
        processor.flush_interval = 0.1
        await processor.start()
        
        # 入队少量数据
        await processor.enqueue({"test": "data"})
        
        # 等待定时刷新
        await asyncio.sleep(0.3)
        
        await processor.stop()
        
        # 验证数据被写入
        assert processor._stats["flushed"] >= 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_storage, processor):
        """测试失败重试"""
        # 第一次调用失败，第二次成功
        mock_storage.write_batch = AsyncMock(
            side_effect=[Exception("DB Error"), None]
        )
        
        await processor.start()
        
        await processor.enqueue({"test": "data"})
        await asyncio.sleep(0.5)
        
        await processor.stop()
        
        # 验证重试
        assert mock_storage.write_batch.call_count == 2
        assert processor._stats["retried"] == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, mock_storage, processor):
        """测试熔断器"""
        # 持续失败
        mock_storage.write_batch = AsyncMock(side_effect=Exception("DB Error"))
        processor.circuit_breaker_threshold = 3
        
        await processor.start()
        
        # 触发多次失败
        for i in range(5):
            await processor.enqueue({"id": i})
        
        await asyncio.sleep(0.5)
        
        # 检查熔断器是否打开
        assert processor._circuit_open is True
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_stop_flush_remaining(self, processor):
        """测试停止时刷新剩余数据"""
        await processor.start()
        
        # 入队但不等待刷新
        for i in range(3):
            await processor.enqueue({"id": i})
        
        # 停止并刷新
        await processor.stop(flush_remaining=True)
        
        assert processor._queue == []
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self, processor):
        """测试统计追踪"""
        await processor.start()
        
        await processor.enqueue({"test": 1})
        await processor.enqueue({"test": 2})
        
        stats = processor.get_stats()
        
        assert stats["enqueued"] == 2
        assert "queue_size" in stats
        assert "circuit_open" in stats
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_high_priority_flush(self, mock_storage):
        """测试高优先级刷新"""
        from app.services.logging.processors.async_processor import PriorityAsyncProcessor
        
        processor = PriorityAsyncProcessor(
            storage=mock_storage,
            batch_size=10
        )
        
        await processor.start()
        
        # 入队不同优先级的日志
        await processor.enqueue({"level": "info", "message": "info log"})
        await processor.enqueue({"level": "critical", "message": "critical log"})
        
        await asyncio.sleep(0.1)
        
        await processor.stop()
        
        # 验证处理
        assert processor._stats["enqueued"] == 2


class TestAsyncBatchProcessorCallbacks:
    """测试回调功能"""
    
    @pytest.mark.asyncio
    async def test_callbacks(self):
        """测试回调函数"""
        on_flush_mock = AsyncMock()
        on_error_mock = AsyncMock()
        on_drop_mock = AsyncMock()
        
        storage = Mock()
        storage.write_batch = AsyncMock()
        
        processor = AsyncBatchProcessor(storage=storage)
        processor.set_callbacks(
            on_flush=on_flush_mock,
            on_error=on_error_mock,
            on_drop=on_drop_mock
        )
        
        await processor.start()
        
        # 触发入队
        await processor.enqueue({"test": "data"})
        await asyncio.sleep(0.1)
        
        await processor.stop()
        
        # 验证回调
        on_flush_mock.assert_called()
