"""
日志存储测试
"""

import pytest
from datetime import datetime, timedelta

from app.services.logging.core import (
    MemoryLogStorage, FileLogStorage,
    get_storage_instance, reset_storage_instances
)
from app.services.logging.models import LogType, LogLevel


class TestMemoryLogStorage:
    """测试内存存储"""
    
    @pytest.fixture
    async def storage(self):
        """存储实例"""
        storage = MemoryLogStorage(max_size=100)
        yield storage
        storage.clear()
    
    @pytest.mark.asyncio
    async def test_write_single(self, storage):
        """测试单条写入"""
        entry = {
            "log_type": LogType.OPERATION.value,
            "level": LogLevel.INFO.value,
            "action": "test",
            "message": "Test message",
            "timestamp": datetime.utcnow()
        }
        
        log_id = await storage.write(entry)
        
        assert log_id is not None
        assert log_id.startswith("mem_")
    
    @pytest.mark.asyncio
    async def test_write_batch(self, storage):
        """测试批量写入"""
        entries = [
            {
                "log_type": LogType.OPERATION.value,
                "level": LogLevel.INFO.value,
                "action": f"action_{i}",
                "message": f"Message {i}",
                "timestamp": datetime.utcnow()
            }
            for i in range(10)
        ]
        
        ids = await storage.write_batch(entries)
        
        assert len(ids) == 10
        assert all(id.startswith("mem_") for id in ids)
    
    @pytest.mark.asyncio
    async def test_query_basic(self, storage):
        """测试基础查询"""
        # 插入测试数据
        for i in range(5):
            await storage.write({
                "log_type": LogType.OPERATION.value,
                "level": LogLevel.INFO.value,
                "action": "test",
                "message": f"Message {i}",
                "timestamp": datetime.utcnow()
            })
        
        results = await storage.query(limit=10)
        
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_query_with_filter(self, storage):
        """测试带过滤条件的查询"""
        # 插入不同类型数据
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "level": LogLevel.INFO.value,
            "action": "test",
            "message": "Operation log",
            "timestamp": datetime.utcnow()
        })
        
        await storage.write({
            "log_type": LogType.ERROR.value,
            "level": LogLevel.ERROR.value,
            "action": "test",
            "message": "Error log",
            "timestamp": datetime.utcnow()
        })
        
        # 按类型查询
        results = await storage.query(log_type=LogType.ERROR.value)
        
        assert len(results) == 1
        assert results[0]["message"] == "Error log"
    
    @pytest.mark.asyncio
    async def test_query_by_user(self, storage):
        """测试按用户查询"""
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "user_id": "user1",
            "action": "test",
            "message": "User 1 log",
            "timestamp": datetime.utcnow()
        })
        
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "user_id": "user2",
            "action": "test",
            "message": "User 2 log",
            "timestamp": datetime.utcnow()
        })
        
        results = await storage.query(user_id="user1")
        
        assert len(results) == 1
        assert results[0]["user_id"] == "user1"
    
    @pytest.mark.asyncio
    async def test_query_time_range(self, storage):
        """测试时间范围查询"""
        now = datetime.utcnow()
        
        # 插入不同时间的日志
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "action": "test",
            "message": "Old log",
            "timestamp": now - timedelta(hours=2)
        })
        
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "action": "test",
            "message": "Recent log",
            "timestamp": now - timedelta(minutes=30)
        })
        
        # 查询最近1小时的日志
        results = await storage.query(
            start_time=now - timedelta(hours=1),
            limit=10
        )
        
        assert len(results) == 1
        assert results[0]["message"] == "Recent log"
    
    @pytest.mark.asyncio
    async def test_query_pagination(self, storage):
        """测试分页查询"""
        # 插入20条数据
        for i in range(20):
            await storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "message": f"Message {i}",
                "timestamp": datetime.utcnow()
            })
        
        # 第一页
        page1 = await storage.query(limit=10, offset=0)
        assert len(page1) == 10
        
        # 第二页
        page2 = await storage.query(limit=10, offset=10)
        assert len(page2) == 10
    
    @pytest.mark.asyncio
    async def test_count(self, storage):
        """测试统计数量"""
        # 插入3条 operation 和 2条 error
        for i in range(3):
            await storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "timestamp": datetime.utcnow()
            })
        
        for i in range(2):
            await storage.write({
                "log_type": LogType.ERROR.value,
                "level": LogLevel.ERROR.value,
                "action": "test",
                "timestamp": datetime.utcnow()
            })
        
        total_count = await storage.count()
        error_count = await storage.count(log_type=LogType.ERROR.value)
        
        assert total_count == 5
        assert error_count == 2
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, storage):
        """测试根据ID获取"""
        entry = {
            "log_type": LogType.OPERATION.value,
            "action": "test",
            "message": "Test message",
            "timestamp": datetime.utcnow()
        }
        
        log_id = await storage.write(entry)
        retrieved = await storage.get_by_id(log_id)
        
        assert retrieved is not None
        assert retrieved["message"] == "Test message"
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, storage):
        """测试获取不存在的ID"""
        result = await storage.get_by_id("non_existent_id")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """测试删除"""
        # 插入数据
        for i in range(5):
            await storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "timestamp": datetime.utcnow()
            })
        
        # 删除前2条
        all_logs = await storage.query(limit=10)
        ids_to_delete = [log["id"] for log in all_logs[:2]]
        
        deleted_count = await storage.delete(ids=ids_to_delete)
        
        assert deleted_count == 2
        assert await storage.count() == 3
    
    @pytest.mark.asyncio
    async def test_delete_by_time(self, storage):
        """测试按时间删除"""
        now = datetime.utcnow()
        
        # 插入旧数据
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "action": "test",
            "timestamp": now - timedelta(hours=2)
        })
        
        # 插入新数据
        await storage.write({
            "log_type": LogType.OPERATION.value,
            "action": "test",
            "timestamp": now
        })
        
        # 删除1小时前的数据
        deleted = await storage.delete(before=now - timedelta(hours=1))
        
        assert deleted == 1
        assert await storage.count() == 1
    
    @pytest.mark.asyncio
    async def test_max_size_limit(self, storage):
        """测试最大容量限制"""
        storage._max_size = 5
        
        # 插入超过限制的数据
        for i in range(10):
            await storage.write({
                "log_type": LogType.OPERATION.value,
                "action": f"action_{i}",
                "timestamp": datetime.utcnow()
            })
        
        # 应该只保留最近的5条
        assert len(storage._logs) == 5
    
    @pytest.mark.asyncio
    async def test_stream_query(self, storage):
        """测试流式查询"""
        # 插入20条数据
        for i in range(20):
            await storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "message": f"Message {i}",
                "timestamp": datetime.utcnow()
            })
        
        # 流式读取
        results = []
        async for log in storage.stream_query(batch_size=5):
            results.append(log)
        
        assert len(results) == 20


class TestStorageFactory:
    """测试存储工厂"""
    
    def setup_method(self):
        """每个测试前重置"""
        reset_storage_instances()
    
    def teardown_method(self):
        """每个测试后清理"""
        reset_storage_instances()
    
    def test_get_memory_storage(self):
        """测试获取内存存储"""
        storage1 = get_storage_instance("memory")
        storage2 = get_storage_instance("memory")
        
        # 应该是同一个实例
        assert storage1 is storage2
    
    def test_get_storage_with_params(self):
        """测试带参数的存储实例"""
        storage1 = get_storage_instance("memory", max_size=100)
        storage2 = get_storage_instance("memory", max_size=200)
        
        # 参数不同应该创建不同实例
        assert storage1 is not storage2
    
    def test_get_invalid_storage_type(self):
        """测试无效的存储类型"""
        with pytest.raises(ValueError, match="Unknown storage type"):
            get_storage_instance("invalid_type")
