"""
CSV 日志导出器
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
import aiofiles
import logging

from app.services.logging.models import ExportResult

logger = logging.getLogger("webapi")


class CSVExporter:
    """CSV 日志导出器"""
    
    def __init__(self, export_dir: str = "exports"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    async def export(
        self,
        logs: List[Dict[str, Any]],
        filename: Optional[str] = None,
        columns: Optional[List[str]] = None,
        include_headers: bool = True,
        delimiter: str = ","
    ) -> ExportResult:
        """
        导出日志到 CSV
        
        Args:
            logs: 日志列表
            filename: 文件名（不含扩展名），默认自动生成
            columns: 指定导出的列，默认导出所有字段
            include_headers: 是否包含表头
            delimiter: 分隔符
        """
        if not logs:
            return ExportResult(
                success=True,
                record_count=0,
                message="No logs to export"
            )
        
        # 生成文件名
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_export_{timestamp}"
        
        file_path = self.export_dir / f"{filename}.csv"
        
        # 确定列
        if not columns:
            # 从所有日志中收集字段
            all_keys = set()
            for log in logs:
                all_keys.update(log.keys())
            columns = sorted(all_keys)
        
        # 写入 CSV
        try:
            async with aiofiles.open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                # 写入表头
                if include_headers:
                    header_line = delimiter.join(self._escape_field(col) for col in columns)
                    await f.write(header_line + '\n')
                
                # 写入数据
                for log in logs:
                    row = []
                    for col in columns:
                        value = log.get(col, "")
                        # 处理嵌套字典
                        if isinstance(value, dict):
                            value = str(value)
                        elif isinstance(value, list):
                            value = "|".join(str(v) for v in value)
                        row.append(self._escape_field(str(value)))
                    
                    await f.write(delimiter.join(row) + '\n')
            
            file_size = file_path.stat().st_size
            
            return ExportResult(
                success=True,
                file_path=str(file_path),
                file_name=file_path.name,
                file_size_bytes=file_size,
                record_count=len(logs),
                format="csv",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"CSV导出失败: {e}")
            return ExportResult(
                success=False,
                record_count=0,
                message=f"Export failed: {str(e)}"
            )
    
    async def export_streaming(
        self,
        log_generator: AsyncGenerator[Dict[str, Any], None],
        filename: Optional[str] = None,
        columns: Optional[List[str]] = None,
        batch_size: int = 1000
    ) -> ExportResult:
        """
        流式导出（用于大量数据）
        
        Args:
            log_generator: 日志异步生成器
            filename: 文件名
            columns: 列定义
            batch_size: 批量写入大小
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_export_{timestamp}"
        
        file_path = self.export_dir / f"{filename}.csv"
        
        try:
            record_count = 0
            headers_written = False
            
            async with aiofiles.open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                batch = []
                
                async for log in log_generator:
                    # 确定列（从第一条数据）
                    if not columns and not headers_written:
                        columns = sorted(log.keys())
                        header_line = ",".join(self._escape_field(col) for col in columns)
                        await f.write(header_line + '\n')
                        headers_written = True
                    
                    # 构建行
                    row = []
                    for col in columns or []:
                        value = log.get(col, "")
                        if isinstance(value, dict):
                            value = str(value)
                        elif isinstance(value, list):
                            value = "|".join(str(v) for v in value)
                        row.append(self._escape_field(str(value)))
                    
                    batch.append(",".join(row))
                    record_count += 1
                    
                    # 批量写入
                    if len(batch) >= batch_size:
                        await f.write('\n'.join(batch) + '\n')
                        batch = []
                
                # 写入剩余
                if batch:
                    await f.write('\n'.join(batch) + '\n')
            
            file_size = file_path.stat().st_size
            
            return ExportResult(
                success=True,
                file_path=str(file_path),
                file_name=file_path.name,
                file_size_bytes=file_size,
                record_count=record_count,
                format="csv"
            )
            
        except Exception as e:
            logger.error(f"CSV流式导出失败: {e}")
            return ExportResult(
                success=False,
                record_count=0,
                message=f"Export failed: {str(e)}"
            )
    
    def _escape_field(self, field: str) -> str:
        """转义 CSV 字段"""
        # 如果包含特殊字符，用引号包裹
        if ',' in field or '"' in field or '\n' in field or '\r' in field:
            # 将双引号替换为两个双引号
            field = field.replace('"', '""')
            return f'"{field}"'
        return field
    
    async def delete_export(self, filename: str) -> bool:
        """删除导出文件"""
        file_path = self.export_dir / filename
        try:
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception as e:
            logger.error(f"删除导出文件失败: {e}")
        return False
    
    def list_exports(self) -> List[Dict[str, Any]]:
        """列出所有导出文件"""
        exports = []
        try:
            for file_path in self.export_dir.glob("*.csv"):
                stat = file_path.stat()
                exports.append({
                    "filename": file_path.name,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime),
                    "path": str(file_path)
                })
        except Exception as e:
            logger.error(f"列出导出文件失败: {e}")
        
        return sorted(exports, key=lambda x: x["created_at"], reverse=True)
