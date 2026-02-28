"""
文件归档器
将日志归档到压缩文件
"""

import gzip
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import aiofiles
import logging

from .base_archiver import LogArchiver

logger = logging.getLogger("webapi")


class FileArchiver(LogArchiver):
    """文件归档器 - 归档到压缩文件"""
    
    def __init__(
        self,
        archive_dir: str = "logs/archive",
        compress: bool = True,
        compression_level: int = 6
    ):
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.compress = compress
        self.compression_level = compression_level
    
    def _get_archive_path(
        self,
        date: datetime,
        log_type: Optional[str] = None
    ) -> Path:
        """获取归档文件路径"""
        type_dir = log_type or "mixed"
        path = self.archive_dir / type_dir / date.strftime("%Y/%m")
        path.mkdir(parents=True, exist_ok=True)
        
        ext = ".jsonl.gz" if self.compress else ".jsonl"
        return path / f"{date.strftime('%Y-%m-%d')}{ext}"
    
    async def archive_batch(self, logs: List[Dict[str, Any]]) -> int:
        """归档一批日志"""
        if not logs:
            return 0
        
        archived_count = 0
        
        # 按日期分组
        logs_by_date: Dict[str, List[Dict]] = {}
        for log in logs:
            ts = log.get("timestamp")
            if not ts:
                continue
            
            if isinstance(ts, datetime):
                date_key = ts.strftime("%Y-%m-%d")
            else:
                date_key = datetime.fromisoformat(str(ts)).strftime("%Y-%m-%d")
            
            logs_by_date.setdefault(date_key, []).append(log)
        
        # 写入各日期文件
        for date_key, date_logs in logs_by_date.items():
            try:
                date = datetime.strptime(date_key, "%Y-%m-%d")
                file_path = self._get_archive_path(date)
                
                # 准备数据
                lines = []
                for log in date_logs:
                    log["archived"] = True
                    log["archive_date"] = datetime.utcnow().isoformat()
                    lines.append(json.dumps(log, ensure_ascii=False, default=str))
                
                # 写入文件
                content = '\n'.join(lines) + '\n'
                
                if self.compress:
                    # 使用 gzip 压缩
                    import asyncio
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._append_gzip,
                        file_path,
                        content
                    )
                else:
                    async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
                        await f.write(content)
                
                archived_count += len(date_logs)
                
            except Exception as e:
                logger.error(f"归档日志失败 {date_key}: {e}")
        
        return archived_count
    
    def _append_gzip(self, file_path: Path, content: str):
        """同步追加 gzip 内容"""
        import gzip
        
        # gzip 不支持追加模式，需要读取、解压、追加、重新压缩
        # 简化处理：如果文件存在，解压后追加
        
        if file_path.exists():
            # 读取现有内容
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                existing = f.read()
            content = existing + content
        
        # 重新写入
        with gzip.open(file_path, 'wt', encoding='utf-8', compresslevel=self.compression_level) as f:
            f.write(content)
    
    async def retrieve(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        log_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """从归档检索日志"""
        results = []
        
        # 确定日期范围
        end_date = end_time or datetime.utcnow()
        start_date = start_time or (end_date - timedelta(days=30))
        
        current_date = end_date
        
        while current_date >= start_date and len(results) < limit:
            file_path = self._get_archive_path(current_date, log_type)
            
            if file_path.exists():
                try:
                    logs = await self._read_archive_file(file_path)
                    
                    # 过滤时间范围
                    for log in logs:
                        log_time = log.get("timestamp")
                        if log_time:
                            if isinstance(log_time, str):
                                log_time = datetime.fromisoformat(log_time)
                            
                            if start_time and log_time < start_time:
                                continue
                            if end_time and log_time > end_time:
                                continue
                        
                        results.append(log)
                        
                        if len(results) >= limit:
                            break
                
                except Exception as e:
                    logger.error(f"读取归档文件失败 {file_path}: {e}")
            
            current_date -= timedelta(days=1)
        
        return results[:limit]
    
    async def _read_archive_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """读取归档文件"""
        logs = []
        
        if file_path.suffix == '.gz':
            # 解压读取
            import asyncio
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                self._read_gzip,
                file_path
            )
        else:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
        
        for line in content.strip().split('\n'):
            if line:
                try:
                    log = json.loads(line)
                    logs.append(log)
                except json.JSONDecodeError:
                    continue
        
        return logs
    
    def _read_gzip(self, file_path: Path) -> str:
        """同步读取 gzip 文件"""
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            return f.read()
    
    async def delete_archive(
        self,
        before: Optional[datetime] = None,
        log_type: Optional[str] = None
    ) -> int:
        """删除归档文件"""
        deleted_count = 0
        
        try:
            if log_type:
                archive_dirs = [self.archive_dir / log_type]
            else:
                archive_dirs = [d for d in self.archive_dir.iterdir() if d.is_dir()]
            
            for archive_dir in archive_dirs:
                for file_path in archive_dir.rglob("*.jsonl*"):
                    # 从文件名解析日期
                    try:
                        date_str = file_path.stem.replace('.jsonl', '')
                        file_date = datetime.strptime(date_str, "%Y-%m-%d")
                        
                        if before and file_date < before:
                            file_path.unlink()
                            deleted_count += 1
                    except ValueError:
                        continue
            
            logger.info(f"删除 {deleted_count} 个归档文件")
            
        except Exception as e:
            logger.error(f"删除归档文件失败: {e}")
        
        return deleted_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取归档统计"""
        stats = {
            "archive_dir": str(self.archive_dir),
            "total_files": 0,
            "total_size_mb": 0,
            "by_type": {}
        }
        
        try:
            total_size = 0
            file_count = 0
            
            for file_path in self.archive_dir.rglob("*"):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    total_size += size
                    file_count += 1
                    
                    # 按类型统计
                    try:
                        rel_parts = file_path.relative_to(self.archive_dir).parts
                        if rel_parts:
                            log_type = rel_parts[0]
                            if log_type not in stats["by_type"]:
                                stats["by_type"][log_type] = {"files": 0, "size_mb": 0}
                            stats["by_type"][log_type]["files"] += 1
                            stats["by_type"][log_type]["size_mb"] += size / (1024 * 1024)
                    except ValueError:
                        pass
            
            stats["total_files"] = file_count
            stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
            
            # 格式化
            for type_stats in stats["by_type"].values():
                type_stats["size_mb"] = round(type_stats["size_mb"], 2)
        
        except Exception as e:
            logger.error(f"获取归档统计失败: {e}")
        
        return stats
    
    async def compress_existing(self, days_old: int = 7) -> int:
        """压缩指定天数之前的未压缩归档"""
        compressed_count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        try:
            for file_path in self.archive_dir.rglob("*.jsonl"):
                if file_path.suffix == '.gz':
                    continue
                
                # 检查文件修改时间
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._compress_file,
                        file_path
                    )
                    compressed_count += 1
        
        except Exception as e:
            logger.error(f"压缩归档文件失败: {e}")
        
        return compressed_count
    
    def _compress_file(self, file_path: Path):
        """同步压缩文件"""
        compressed_path = file_path.with_suffix('.jsonl.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb', compresslevel=self.compression_level) as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        file_path.unlink()  # 删除原文件
