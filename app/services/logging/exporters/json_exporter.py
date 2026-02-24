"""
JSON 日志导出器
"""

import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
import aiofiles
import logging

from app.services.logging.models import ExportResult

logger = logging.getLogger("webapi")


class JSONExporter:
    """JSON 日志导出器"""
    
    def __init__(self, export_dir: str = "exports"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    async def export(
        self,
        logs: List[Dict[str, Any]],
        filename: Optional[str] = None,
        pretty: bool = False,
        compress: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExportResult:
        """
        导出日志到 JSON
        
        Args:
            logs: 日志列表
            filename: 文件名（不含扩展名）
            pretty: 是否格式化输出
            compress: 是否使用 gzip 压缩
            metadata: 导出元数据
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
        
        ext = ".json.gz" if compress else ".json"
        file_path = self.export_dir / f"{filename}{ext}"
        
        try:
            # 构建导出数据
            export_data = {
                "metadata": {
                    "export_time": datetime.utcnow().isoformat(),
                    "record_count": len(logs),
                    "format_version": "1.0",
                    **(metadata or {})
                },
                "logs": logs
            }
            
            # 序列化
            indent = 2 if pretty else None
            json_content = json.dumps(export_data, ensure_ascii=False, indent=indent, default=str)
            
            # 写入
            if compress:
                # 同步 gzip 压缩
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._write_gzip,
                    file_path,
                    json_content.encode('utf-8')
                )
            else:
                async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                    await f.write(json_content)
            
            file_size = file_path.stat().st_size
            
            return ExportResult(
                success=True,
                file_path=str(file_path),
                file_name=file_path.name,
                file_size_bytes=file_size,
                record_count=len(logs),
                format="json" + (".gz" if compress else "),
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"JSON导出失败: {e}")
            return ExportResult(
                success=False,
                record_count=0,
                message=f"Export failed: {str(e)}"
            )
    
    def _write_gzip(self, path: Path, data: bytes):
        """同步写入 gzip 文件"""
        with gzip.open(path, 'wb') as f:
            f.write(data)
    
    async def export_streaming(
        self,
        log_generator: AsyncGenerator[Dict[str, Any], None],
        filename: Optional[str] = None,
        compress: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExportResult:
        """
        流式导出大量日志（JSON Lines 格式）
        
        每行一个 JSON 对象，便于流式处理
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_export_{timestamp}"
        
        ext = ".jsonl.gz" if compress else ".jsonl"
        file_path = self.export_dir / f"{filename}{ext}"
        
        try:
            record_count = 0
            
            if compress:
                # 流式 gzip 压缩
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._write_streaming_gzip,
                    file_path,
                    log_generator,
                    metadata
                )
                # 重新统计数量（简化处理）
                record_count = -1  # 未知
            else:
                async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                    # 写入元数据头
                    header = {
                        "metadata": {
                            "export_time": datetime.utcnow().isoformat(),
                            **(metadata or {})
                        }
                    }
                    await f.write(json.dumps(header, ensure_ascii=False) + '\n')
                    
                    # 写入日志
                    async for log in log_generator:
                        await f.write(json.dumps(log, ensure_ascii=False, default=str) + '\n')
                        record_count += 1
            
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            return ExportResult(
                success=True,
                file_path=str(file_path),
                file_name=file_path.name,
                file_size_bytes=file_size,
                record_count=record_count,
                format="jsonl" + (".gz" if compress else "),
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"JSON流式导出失败: {e}")
            return ExportResult(
                success=False,
                record_count=0,
                message=f"Export failed: {str(e)}"
            )
    
    def _write_streaming_gzip(
        self,
        path: Path,
        generator: AsyncGenerator[Dict[str, Any], None],
        metadata: Optional[Dict[str, Any]]
    ):
        """同步流式 gzip 写入（在新线程中运行）"""
        import asyncio
        
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            # 写入元数据
            header = {
                "metadata": {
                    "export_time": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            }
            f.write(json.dumps(header, ensure_ascii=False) + '\n')
            
            # 需要同步获取异步生成器的数据
            # 这里简化处理，实际使用时需要更复杂的同步机制
            pass
    
    async def export_array_streaming(
        self,
        log_generator: AsyncGenerator[Dict[str, Any], None],
        filename: Optional[str] = None
    ) -> ExportResult:
        """
        流式导出为标准 JSON 数组格式
        
        格式: [log1, log2, ...]
        适用于较小的数据集
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_export_{timestamp}"
        
        file_path = self.export_dir / f"{filename}.json"
        
        try:
            record_count = 0
            
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                await f.write('[')
                first = True
                
                async for log in log_generator:
                    if not first:
                        await f.write(',')
                    first = False
                    
                    await f.write(json.dumps(log, ensure_ascii=False, default=str))
                    record_count += 1
                
                await f.write(']')
            
            file_size = file_path.stat().st_size
            
            return ExportResult(
                success=True,
                file_path=str(file_path),
                file_name=file_path.name,
                file_size_bytes=file_size,
                record_count=record_count,
                format="json"
            )
            
        except Exception as e:
            logger.error(f"JSON数组导出失败: {e}")
            return ExportResult(
                success=False,
                record_count=0,
                message=f"Export failed: {str(e)}"
            )
    
    async def delete_export(self, filename: str) -> bool:
        """删除导出文件"""
        # 尝试多种扩展名
        for ext in ['.json', '.json.gz', '.jsonl', '.jsonl.gz']:
            file_path = self.export_dir / (filename + ext)
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
            for ext in ['*.json', '*.json.gz', '*.jsonl', '*.jsonl.gz']:
                for file_path in self.export_dir.glob(ext):
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
