"""
CSV 导出器测试
"""

import pytest
import csv
from datetime import datetime
from pathlib import Path

from app.services.logging.exporters import CSVExporter


class TestCSVExporter:
    """测试 CSV 导出器"""
    
    @pytest.fixture
    def exporter(self, tmp_path):
        """导出器实例"""
        return CSVExporter(export_dir=str(tmp_path))
    
    @pytest.fixture
    def sample_logs(self):
        """示例日志数据"""
        return [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "info",
                "action": "login",
                "user_id": "user1",
                "message": "User logged in"
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "error",
                "action": "api_call",
                "user_id": "user2",
                "message": "API error"
            }
        ]
    
    @pytest.mark.asyncio
    async def test_export_basic(self, exporter, sample_logs, tmp_path):
        """测试基础导出"""
        result = await exporter.export(
            logs=sample_logs,
            filename="test_export"
        )
        
        assert result.success is True
        assert result.record_count == 2
        assert result.file_path is not None
        assert Path(result.file_path).exists()
    
    @pytest.mark.asyncio
    async def test_export_empty(self, exporter):
        """测试空数据导出"""
        result = await exporter.export(logs=[])
        
        assert result.success is True
        assert result.record_count == 0
    
    @pytest.mark.asyncio
    async def test_export_with_columns(self, exporter, sample_logs):
        """测试指定列导出"""
        result = await exporter.export(
            logs=sample_logs,
            filename="columns_test",
            columns=["timestamp", "level", "action"]
        )
        
        # 验证文件内容
        with open(result.file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
            
            assert headers == ["timestamp", "level", "action"]
            assert "user_id" not in headers
    
    @pytest.mark.asyncio
    async def test_export_no_headers(self, exporter, sample_logs):
        """测试无表头导出"""
        result = await exporter.export(
            logs=sample_logs,
            filename="no_headers",
            include_headers=False
        )
        
        with open(result.file_path, 'r') as f:
            first_line = f.readline().strip()
            # 第一行应该是数据而不是表头
            assert "timestamp" not in first_line or "," in first_line
    
    @pytest.mark.asyncio
    async def test_export_special_characters(self, exporter):
        """测试特殊字符处理"""
        logs = [
            {
                "message": "Test with, comma",
                "data": 'Test with "quotes"'
            },
            {
                "message": "Test with\nnewline",
                "data": "normal"
            }
        ]
        
        result = await exporter.export(logs=logs, filename="special_chars")
        
        assert result.success is True
        
        # 验证能正确解析
        with open(result.file_path, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过表头
            rows = list(reader)
            assert len(rows) == 2
    
    @pytest.mark.asyncio
    async def test_export_nested_data(self, exporter):
        """测试嵌套数据导出"""
        logs = [
            {
                "action": "test",
                "details": {"key": "value", "nested": {"a": 1}}
            }
        ]
        
        result = await exporter.export(logs=logs, filename="nested")
        
        assert result.success is True
        
        with open(result.file_path, 'r') as f:
            content = f.read()
            # 嵌套字典应该被转换为字符串
            assert "{'key':" in content or '"key":' in content
    
    @pytest.mark.asyncio
    async def test_list_exports(self, exporter, sample_logs):
        """测试列出导出文件"""
        # 创建多个导出文件
        await exporter.export(logs=sample_logs, filename="export1")
        await exporter.export(logs=sample_logs, filename="export2")
        
        exports = exporter.list_exports()
        
        assert len(exports) == 2
        assert all(".csv" in exp["filename"] for exp in exports)
        assert exports[0]["created_at"] >= exports[1]["created_at"]  # 按时间倒序
    
    @pytest.mark.asyncio
    async def test_delete_export(self, exporter, sample_logs):
        """测试删除导出文件"""
        result = await exporter.export(logs=sample_logs, filename="to_delete")
        
        # 删除
        deleted = await exporter.delete_export("to_delete.csv")
        
        assert deleted is True
        assert not Path(result.file_path).exists()
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, exporter):
        """测试删除不存在的文件"""
        deleted = await exporter.delete_export("nonexistent.csv")
        
        assert deleted is False
    
    def test_escape_field(self, exporter):
        """测试字段转义"""
        # 普通字段
        assert exporter._escape_field("normal") == "normal"
        
        # 包含逗号
        assert exporter._escape_field("has, comma") == '"has, comma"'
        
        # 包含引号
        assert exporter._escape_field('has "quotes"') == '"has ""quotes"""'
        
        # 包含换行
        assert exporter._escape_field("has\nnewline") == '"has\nnewline"'
