"""
日志服务主类
整合所有功能的统一接口
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import logging

from .core import MongoLogStorage, LogRotationPolicy, LogRotator, LogIndexer
from .processors import AsyncBatchProcessor, LogQueue, FilterProcessor
from .analyzers import UserBehaviorAnalyzer, SecurityAnalyzer, PerformanceAnalyzer, AnomalyDetector
from .exporters import CSVExporter, JSONExporter, ExcelExporter
from .archivers import FileArchiver, MongoArchiver
from .models import (
    LogEntry, LogType, LogLevel,
    UserActivityStats, SecurityStats, SystemHealthStats,
    ExportResult
)

logger = logging.getLogger("webapi")


class LogService:
    """
    统一日志服务
    
    提供日志记录、查询、分析、导出的一站式服务
    """
    
    def __init__(
        self,
        storage=None,
        enable_async_processor: bool = True,
        enable_archiver: bool = True,
        export_dir: str = "exports"
    ):
        # 存储
        self.storage = storage or MongoLogStorage()
        
        # 处理器
        self.async_processor: Optional[AsyncBatchProcessor] = None
        if enable_async_processor:
            self.async_processor = AsyncBatchProcessor(
                storage=self.storage,
                queue_config=LogQueue(max_size=10000)
            )
        
        # 归档器
        self.archiver = None
        if enable_archiver:
            self.archiver = FileArchiver()
        
        # 分析器
        self.user_analyzer = UserBehaviorAnalyzer(self.storage)
        self.security_analyzer = SecurityAnalyzer(self.storage)
        self.performance_analyzer = PerformanceAnalyzer(self.storage)
        self.anomaly_detector = AnomalyDetector(self.storage)
        
        # 导出器
        self.csv_exporter = CSVExporter(export_dir)
        self.json_exporter = JSONExporter(export_dir)
        self.excel_exporter = ExcelExporter(export_dir)
        
        # 索引管理
        self.indexer = LogIndexer()
        
        # 轮转器
        self.rotator: Optional[LogRotator] = None
        if enable_archiver and self.archiver:
            policy = LogRotationPolicy()
            self.rotator = LogRotator(self.storage, self.archiver, policy)
        
        self._started = False
    
    async def start(self):
        """启动服务"""
        if self._started:
            return
        
        if self.async_processor:
            await self.async_processor.start()
        
        # 创建索引
        await self.indexer.create_indexes()
        
        self._started = True
        logger.info("LogService started")
    
    async def stop(self):
        """停止服务"""
        if not self._started:
            return
        
        if self.async_processor:
            await self.async_processor.stop(flush_remaining=True)
        
        self._started = False
        logger.info("LogService stopped")
    
    # ========== 日志写入 ==========
    
    async def write_log(
        self,
        log_type: Union[str, LogType],
        level: Union[str, LogLevel],
        action: str,
        message: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        写入单条日志
        
        Args:
            log_type: 日志类型
            level: 日志级别
            action: 动作
            message: 消息
            user_id: 用户ID
            username: 用户名
            **kwargs: 其他字段
            
        Returns:
            是否成功
        """
        entry = {
            "log_type": log_type.value if isinstance(log_type, LogType) else log_type,
            "level": level.value if isinstance(level, LogLevel) else level,
            "action": action,
            "message": message,
            "timestamp": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        
        if user_id:
            entry["user_id"] = user_id
        if username:
            entry["username"] = username
        
        entry.update(kwargs)
        
        try:
            if self.async_processor:
                return await self.async_processor.enqueue(entry)
            else:
                await self.storage.write(entry)
                return True
        except Exception as e:
            logger.error(f"写入日志失败: {e}")
            return False
    
    async def write_logs_batch(self, entries: List[Dict[str, Any]]) -> int:
        """批量写入日志"""
        if not entries:
            return 0
        
        success_count = 0
        for entry in entries:
            if await self.write_log(**entry):
                success_count += 1
        
        return success_count
    
    # ========== 日志查询 ==========
    
    async def query_logs(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        days: int = 7,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """查询日志"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        return await self.storage.query(
            log_type=log_type,
            level=level,
            user_id=user_id,
            start_time=start_time,
            limit=limit,
            offset=offset
        )
    
    async def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取日志"""
        return await self.storage.get_by_id(log_id)
    
    async def count_logs(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        days: int = 7
    ) -> int:
        """统计日志数量"""
        start_time = datetime.utcnow() - timedelta(days=days)
        return await self.storage.count(
            log_type=log_type,
            level=level,
            start_time=start_time
        )
    
    # ========== 日志导出 ==========
    
    async def export_logs(
        self,
        format: str = "csv",
        days: int = 7,
        log_type: Optional[str] = None,
        user_id: Optional[str] = None,
        filename: Optional[str] = None
    ) -> ExportResult:
        """
        导出日志
        
        Args:
            format: 导出格式 (csv/json/excel)
            days: 导出最近几天的日志
            log_type: 指定日志类型
            user_id: 指定用户
            filename: 文件名
        """
        # 查询日志
        logs = await self.query_logs(
            log_type=log_type,
            user_id=user_id,
            days=days,
            limit=50000  # 限制最大导出数量
        )
        
        if not logs:
            return ExportResult(
                success=True,
                record_count=0,
                message="No logs to export"
            )
        
        # 生成文件名
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_{log_type or 'all'}_{days}d_{timestamp}"
        
        # 导出
        if format == "csv":
            return await self.csv_exporter.export(logs, filename=filename)
        elif format == "json":
            return await self.json_exporter.export(logs, filename=filename)
        elif format == "excel":
            return await self.excel_exporter.export(logs, filename=filename)
        else:
            return ExportResult(
                success=False,
                record_count=0,
                message=f"Unsupported format: {format}"
            )
    
    # ========== 日志分析 ==========
    
    async def analyze_user_activity(
        self,
        user_id: str,
        days: int = 30
    ) -> UserActivityStats:
        """分析用户活动"""
        return await self.user_analyzer.analyze_user_activity(user_id, days=days)
    
    async def analyze_security(self, hours: int = 24) -> SecurityStats:
        """安全分析"""
        return await self.security_analyzer.analyze_security(hours=hours)
    
    async def analyze_system_health(self, hours: int = 24) -> SystemHealthStats:
        """系统健康分析"""
        return await self.performance_analyzer.analyze_system_health(hours=hours)
    
    async def detect_anomalies(
        self,
        user_id: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """检测异常"""
        return await self.anomaly_detector.detect_anomalies(user_id, hours=hours)
    
    # ========== 日志归档 ==========
    
    async def archive_old_logs(self, days: int = 90) -> Dict[str, Any]:
        """归档旧日志"""
        if not self.rotator:
            return {"error": "Archiver not enabled"}
        
        return await self.rotator.rotate_all()
    
    async def get_archive_stats(self) -> Dict[str, Any]:
        """获取归档统计"""
        if self.archiver:
            return await self.archiver.get_stats()
        return {}
    
    # ========== 统计信息 ==========
    
    def get_processor_stats(self) -> Dict[str, Any]:
        """获取处理器统计"""
        if self.async_processor:
            return self.async_processor.get_stats()
        return {}
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        return await self.rotator.get_storage_stats() if self.rotator else {}


# 全局服务实例
_log_service: Optional[LogService] = None


def get_log_service() -> LogService:
    """获取日志服务实例（单例）"""
    global _log_service
    if _log_service is None:
        _log_service = LogService()
    return _log_service


async def init_log_service():
    """初始化日志服务"""
    service = get_log_service()
    await service.start()
    return service


async def shutdown_log_service():
    """关闭日志服务"""
    service = get_log_service()
    await service.stop()
