"""
文件归档器测试
"""

import pytest
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path

from app.services.logging.archivers import FileArchiver


class TestFileArchiver:
    """测试文件归档器"""
    
    @pytest.fixture
    def archiver(self, tmp_path):
        """归档器实例"""
        return FileArchiver(
            archive_dir=str(tmp_path / "archive"),
            compress=True
        )
    
    @pytest.fixture
    def sample_logs(self):
        """示例日志"""
        now = datetime.utcnow()
        return [
            {
                "id": f"log_{i}",
                "message": f"Message {i}",
                "timestamp": now - timedelta(hours=i)
            }
            for i in range(5)
        ]
    
    @pytest.mark.asyncio
    async def test_archive_batch(self, archiver, sample_logs, tmp_path):
        """测试批量归档"""
        count = await archiver.archive_batch(sample_logs)
        
        assert count == 5
        
        # 验证文件创建
        archive_files = list(Path(archiver.archive_dir).rglob("*.jsonl.gz"))
        assert len(archive_files) >= 1
    
    @pytest.mark.asyncio
    async def test_archive_empty(self, archiver):
        """测试空数据归档"""
        count = await archiver.archive_batch([])
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_archive_by_date(self, archiver):
        """测试按日期归档"""
        # 不同日期的日志
        logs = [
            {
                "id": "1",
                "timestamp": datetime(2024, 1, 15, 10, 0)
            },
            {
                "id": "2",
                "timestamp": datetime(2024, 1, 16, 10, 0)
            }
        ]
        
        count = await archiver.archive_batch(logs)
        
        assert count == 2
        
        # 应该创建两个文件
        files = list(Path(archiver.archive_dir).rglob("*.jsonl.gz"))
        assert len(files) == 2
    
    @pytest.mark.asyncio
    async def test_retrieve(self, archiver, sample_logs):
        """测试检索"""
        # 先归档
        await archiver.archive_batch(sample_logs)
        
        # 再检索
        retrieved = await archiver.retrieve(
            start_time=datetime.utcnow() - timedelta(days=1),
            limit=10
        )
        
        assert len(retrieved) == 5
    
    @pytest.mark.asyncio
    async def test_retrieve_time_range(self, archiver):
        """测试时间范围检索"""
        now = datetime.utcnow()
        
        logs = [
            {"id": "old", "timestamp": now - timedelta(days=2)},
            {"id": "recent", "timestamp": now - timedelta(hours=1)}
        ]
        
        await archiver.archive_batch(logs)
        
        # 只检索最近1天的
        retrieved = await archiver.retrieve(
            start_time=now - timedelta(hours=12),
            limit=10
        )
        
        assert len(retrieved) == 1
        assert retrieved[0]["id"] == "recent"
    
    @pytest.mark.asyncio
    async def test_retrieve_limit(self, archiver, sample_logs):
        """测试检索限制"""
        await archiver.archive_batch(sample_logs)
        
        retrieved = await archiver.retrieve(limit=3)
        
        assert len(retrieved) == 3
    
    @pytest.mark.asyncio
    async def test_get_stats(self, archiver, sample_logs):
        """测试统计信息"""
        await archiver.archive_batch(sample_logs)
        
        stats = await archiver.get_stats()
        
        assert stats["total_files"] >= 1
        assert stats["total_size_mb"] > 0
        assert "by_type" in stats
    
    @pytest.mark.asyncio
    async def test_delete_archive(self, archiver, sample_logs):
        """测试删除归档"""
        await archiver.archive_batch(sample_logs)
        
        # 获取文件路径
        files_before = list(Path(archiver.archive_dir).rglob("*.jsonl.gz"))
        assert len(files_before) > 0
        
        # 删除旧归档
        deleted = await archiver.delete_archive(
            before=datetime.utcnow() + timedelta(days=1)
        )
        
        assert deleted >= 1
    
    @pytest.mark.asyncio
    async def test_compress_existing(self, archiver, tmp_path):
        """测试压缩现有文件"""
        # 创建未压缩文件
        archive_dir = Path(archiver.archive_dir) / "mixed" / "2024" / "01"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        uncompressed_file = archive_dir / "2024-01-15.jsonl"
        uncompressed_file.write_text('{"test": "data"}\n')
        
        # 修改文件时间为7天前
        old_time = (datetime.utcnow() - timedelta(days=10)).timestamp()
        uncompressed_file.touch()
        
        # 压缩
        compressed = await archiver.compress_existing(days_old=7)
        
        assert compressed >= 1
        
        # 验证压缩文件存在
        compressed_file = archive_dir / "2024-01-15.jsonl.gz"
        assert compressed_file.exists()
        assert not uncompressed_file.exists()
    
    def test_get_archive_path(self, archiver):
        """测试归档路径生成"""
        date = datetime(2024, 1, 15)
        
        path = archiver._get_archive_path(date, log_type="operation")
        
        assert "operation" in str(path)
        assert "2024" in str(path)
        assert "01" in str(path)
        assert "2024-01-15" in str(path)
    
    def test_read_gzip(self, archiver, tmp_path):
        """测试 gzip 读取"""
        # 创建测试 gzip 文件
        gz_file = tmp_path / "test.jsonl.gz"
        
        with gzip.open(gz_file, 'wt', encoding='utf-8') as f:
            f.write('{"id": "1"}\n{"id": "2"}\n')
        
        content = archiver._read_gzip(gz_file)
        
        assert '{"id": "1"}' in content
        assert '{"id": "2"}' in content
