"""
日志轮转测试
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from app.services.logging.core import (
    LogRotationPolicy, LogRotator, LogCompressor
)
from app.services.logging.models import LogType


class TestLogRotationPolicy:
    """测试轮转策略"""
    
    def test_default_retention(self):
        """测试默认保留策略"""
        policy = LogRotationPolicy()
        
        assert policy.get_retention_days(LogType.OPERATION.value) == 90
        assert policy.get_retention_days(LogType.AUDIT.value) == 365
        assert policy.get_retention_days(LogType.ERROR.value) == 180
    
    def test_custom_retention(self):
        """测试自定义保留策略"""
        policy = LogRotationPolicy(
            retention_days={
                "operation": 30,
                "custom_type": 60
            }
        )
        
        assert policy.get_retention_days("operation") == 30
        assert policy.get_retention_days("custom_type") == 60
        assert policy.get_retention_days("unknown") == 30  # 默认值
    
    def test_should_archive(self):
        """测试归档判断"""
        policy = LogRotationPolicy(archive_enabled=True)
        
        assert policy.should_archive(LogType.OPERATION.value) is True
        
        policy.archive_enabled = False
        assert policy.should_archive(LogType.OPERATION.value) is False


class TestLogRotator:
    """测试日志轮转器"""
    
    @pytest.fixture
    def mock_storage(self):
        """模拟存储"""
        storage = Mock()
        storage.delete = AsyncMock(return_value=10)
        return storage
    
    @pytest.fixture
    def mock_archiver(self):
        """模拟归档器"""
        archiver = Mock()
        archiver.archive_batch = AsyncMock(return_value=10)
        return archiver
    
    @pytest.fixture
    def policy(self):
        """轮转策略"""
        return LogRotationPolicy(
            retention_days={"operation": 30, "audit": 90},
            archive_enabled=True
        )
    
    @pytest.mark.asyncio
    async def test_rotate_single_type(self, mock_storage, mock_archiver, policy):
        """测试单类型轮转"""
        # 模拟流式查询
        old_logs = [
            {"id": f"log_{i}", "timestamp": datetime.utcnow() - timedelta(days=40)}
            for i in range(10)
        ]
        mock_storage.stream_query = AsyncMock()
        mock_storage.stream_query.return_value = self._async_generator(old_logs)
        
        rotator = LogRotator(mock_storage, mock_archiver, policy)
        
        result = await rotator.rotate(LogType.OPERATION.value)
        
        assert result["log_type"] == LogType.OPERATION.value
        assert result["archived"] is True
        assert result["deleted_count"] == 10
        mock_storage.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rotate_force(self, mock_storage, mock_archiver, policy):
        """测试强制轮转"""
        mock_storage.stream_query = AsyncMock()
        mock_storage.stream_query.return_value = self._async_generator([])
        
        rotator = LogRotator(mock_storage, mock_archiver, policy)
        
        # 强制轮转（不过滤时间）
        result = await rotator.rotate(LogType.OPERATION.value, force=True)
        
        # 强制轮转时不应该调用归档
        assert result["archived"] is False
    
    @pytest.mark.asyncio
    async def test_rotate_all_types(self, mock_storage, mock_archiver, policy):
        """测试轮转所有类型"""
        mock_storage.stream_query = AsyncMock()
        mock_storage.stream_query.return_value = self._async_generator([])
        
        rotator = LogRotator(mock_storage, mock_archiver, policy)
        
        results = await rotator.rotate_all()
        
        # 应该为每种日志类型生成结果
        assert LogType.OPERATION.value in results
        assert LogType.AUDIT.value in results
        assert LogType.ERROR.value in results
    
    def _async_generator(self, items):
        """创建异步生成器"""
        async def gen():
            for item in items:
                yield item
        return gen()
    
    @pytest.mark.asyncio
    async def test_archive_logs_error_handling(self, mock_storage, mock_archiver, policy):
        """测试归档错误处理"""
        mock_archiver.archive_batch = AsyncMock(side_effect=Exception("Archive failed"))
        mock_storage.stream_query = AsyncMock()
        mock_storage.stream_query.return_value = self._async_generator([{"id": "1"}])
        
        rotator = LogRotator(mock_storage, mock_archiver, policy)
        
        with pytest.raises(Exception, match="Archive failed"):
            await rotator._archive_logs(LogType.OPERATION.value, datetime.utcnow())


class TestLogCompressor:
    """测试日志压缩器"""
    
    @pytest.fixture
    def compressor(self):
        return LogCompressor(format="gzip")
    
    @pytest.mark.asyncio
    async def test_compress_decompress(self, compressor, tmp_path):
        """测试压缩和解压"""
        # 创建测试文件
        test_file = tmp_path / "test.jsonl"
        test_content = '{"test": "data"}\n{"test": "data2"}\n'
        test_file.write_text(test_content)
        
        # 压缩
        compressed = await compressor.compress_file(test_file)
        
        assert compressed.suffix == ".gz"
        assert compressed.exists()
        assert not test_file.exists()  # 原文件应被删除
        
        # 解压
        decompressed = await compressor.decompress_file(compressed)
        
        assert decompressed.read_text() == test_content
