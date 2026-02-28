"""
日志轮转与归档管理
"""

import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import asyncio
import aiofiles
import logging

from app.services.logging.models import LogType, DEFAULT_LOG_TYPE_CONFIGS

logger = logging.getLogger("webapi")


class LogRotationPolicy:
    """日志轮转策略配置"""
    
    def __init__(
        self,
        retention_days: Optional[Dict[str, int]] = None,
        archive_enabled: bool = True,
        archive_storage: str = "file",
        archive_path: str = "logs/archive",
        compress: bool = True,
        compression_format: str = "gzip",
        schedule: str = "0 2 * * *",  # 每天凌晨2点
        max_archive_size_mb: float = 100,
        cleanup_empty_dirs: bool = True
    ):
        self.retention_days = retention_days or {
            log_type: config.retention_days
            for log_type, config in DEFAULT_LOG_TYPE_CONFIGS.items()
        }
        self.archive_enabled = archive_enabled
        self.archive_storage = archive_storage
        self.archive_path = Path(archive_path)
        self.compress = compress
        self.compression_format = compression_format
        self.schedule = schedule
        self.max_archive_size_mb = max_archive_size_mb
        self.cleanup_empty_dirs = cleanup_empty_dirs
    
    def get_retention_days(self, log_type: str) -> int:
        """获取指定日志类型的保留天数"""
        return self.retention_days.get(log_type, 30)
    
    def should_archive(self, log_type: str) -> bool:
        """判断是否应该归档该类型日志"""
        if not self.archive_enabled:
            return False
        return DEFAULT_LOG_TYPE_CONFIGS.get(log_type, LogTypeConfig()).archive_enabled


class LogRotator:
    """日志轮转管理器"""
    
    def __init__(
        self,
        storage,
        archiver,
        policy: LogRotationPolicy
    ):
        self.storage = storage
        self.archiver = archiver
        self.policy = policy
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start_scheduler(self):
        """启动定时轮转任务"""
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Log rotator scheduler started")
    
    async def stop_scheduler(self):
        """停止定时轮转任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Log rotator scheduler stopped")
    
    async def _scheduler_loop(self):
        """调度器循环"""
        import aiocron
        
        @aiocron.crontab(self.policy.schedule)
        async def scheduled_rotation():
            await self.rotate_all()
        
        while self._running:
            await asyncio.sleep(60)
    
    async def rotate_all(self) -> Dict[str, Any]:
        """轮转所有类型的日志"""
        results = {}
        
        for log_type in LogType:
            try:
                result = await self.rotate(log_type.value)
                results[log_type.value] = result
            except Exception as e:
                logger.error(f"轮转日志失败 {log_type.value}: {e}")
                results[log_type.value] = {"error": str(e)}
        
        return results
    
    async def rotate(
        self,
        log_type: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        执行日志轮转
        
        Args:
            log_type: 日志类型
            force: 是否强制轮转（忽略保留策略）
        """
        start_time = datetime.utcnow()
        
        # 计算截止时间
        if force:
            cutoff_date = datetime.utcnow()
        else:
            retention_days = self.policy.get_retention_days(log_type)
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        result = {
            "log_type": log_type,
            "cutoff_date": cutoff_date.isoformat(),
            "archived": False,
            "archived_count": 0,
            "deleted_count": 0,
            "errors": []
        }
        
        try:
            # 1. 归档旧日志
            if self.policy.should_archive(log_type) and not force:
                archived_count = await self._archive_logs(log_type, cutoff_date)
                result["archived"] = True
                result["archived_count"] = archived_count
            
            # 2. 删除过期日志
            deleted_count = await self.storage.delete(
                log_type=log_type,
                before=cutoff_date
            )
            result["deleted_count"] = deleted_count
            
            # 3. 清理空目录
            if self.policy.cleanup_empty_dirs:
                await self._cleanup_empty_dirs(log_type)
            
        except Exception as e:
            logger.error(f"日志轮转失败 {log_type}: {e}")
            result["errors"].append(str(e))
        
        result["duration_ms"] = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        logger.info(
            f"日志轮转完成: {log_type}, "
            f"归档={result['archived_count']}, "
            f"删除={result['deleted_count']}"
        )
        
        return result
    
    async def _archive_logs(
        self,
        log_type: str,
        before: datetime
    ) -> int:
        """归档旧日志"""
        archived_count = 0
        batch_size = 1000
        
        try:
            # 流式查询并归档
            batch = []
            async for log in self.storage.stream_query(
                log_type=log_type,
                end_time=before,
                batch_size=batch_size
            ):
                batch.append(log)
                
                if len(batch) >= batch_size:
                    await self.archiver.archive_batch(batch)
                    archived_count += len(batch)
                    batch = []
            
            # 归档剩余
            if batch:
                await self.archiver.archive_batch(batch)
                archived_count += len(batch)
            
            return archived_count
            
        except Exception as e:
            logger.error(f"归档日志失败 {log_type}: {e}")
            raise
    
    async def _cleanup_empty_dirs(self, log_type: str):
        """清理空目录"""
        try:
            archive_dir = self.policy.archive_path / log_type
            if not archive_dir.exists():
                return
            
            # 递归删除空目录
            for path in sorted(archive_dir.rglob("*"), reverse=True):
                if path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
                    
        except Exception as e:
            logger.warning(f"清理空目录失败: {e}")
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        stats = {
            "archive_path": str(self.policy.archive_path),
            "archive_size_mb": 0,
            "archive_file_count": 0,
            "by_type": {}
        }
        
        try:
            if self.policy.archive_path.exists():
                total_size = 0
                file_count = 0
                
                for file_path in self.policy.archive_path.rglob("*"):
                    if file_path.is_file():
                        size = file_path.stat().st_size
                        total_size += size
                        file_count += 1
                        
                        # 按类型统计
                        rel_parts = file_path.relative_to(self.policy.archive_path).parts
                        if rel_parts:
                            log_type = rel_parts[0]
                            if log_type not in stats["by_type"]:
                                stats["by_type"][log_type] = {"size_mb": 0, "count": 0}
                            stats["by_type"][log_type]["size_mb"] += size / (1024 * 1024)
                            stats["by_type"][log_type]["count"] += 1
                
                stats["archive_size_mb"] = round(total_size / (1024 * 1024), 2)
                stats["archive_file_count"] = file_count
                
                # 格式化大小
                for type_stats in stats["by_type"].values():
                    type_stats["size_mb"] = round(type_stats["size_mb"], 2)
        
        except Exception as e:
            logger.error(f"获取存储统计失败: {e}")
        
        return stats


class LogCompressor:
    """日志压缩工具"""
    
    def __init__(self, format: str = "gzip"):
        self.format = format
    
    async def compress_file(self, file_path: Path) -> Path:
        """压缩单个文件"""
        if self.format == "gzip":
            return await self._gzip_compress(file_path)
        else:
            raise ValueError(f"Unsupported compression format: {self.format}")
    
    async def _gzip_compress(self, file_path: Path) -> Path:
        """Gzip压缩"""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        # 使用线程池执行同步IO操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._do_gzip_compress,
            file_path,
            compressed_path
        )
        
        return compressed_path
    
    def _do_gzip_compress(self, src: Path, dst: Path):
        """执行gzip压缩（同步）"""
        with open(src, 'rb') as f_in:
            with gzip.open(dst, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        src.unlink()  # 删除原文件
    
    async def decompress_file(self, file_path: Path) -> Path:
        """解压文件"""
        if file_path.suffix == '.gz':
            return await self._gzip_decompress(file_path)
        return file_path
    
    async def _gzip_decompress(self, file_path: Path) -> Path:
        """Gzip解压"""
        decompressed_path = file_path.with_suffix('')
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._do_gzip_decompress,
            file_path,
            decompressed_path
        )
        
        return decompressed_path
    
    def _do_gzip_decompress(self, src: Path, dst: Path):
        """执行gzip解压（同步）"""
        with gzip.open(src, 'rb') as f_in:
            with open(dst, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
