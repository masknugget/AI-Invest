"""
日志存储抽象层
支持 MongoDB、文件、内存等多种存储后端
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
import asyncio
import aiofiles
import logging

from bson import ObjectId

from app.core.database import get_mongo_db
from app.services.logging.models import LogEntry, LogType, LogLevel

logger = logging.getLogger("webapi")


class LogStorage(ABC):
    """日志存储抽象基类"""
    
    @abstractmethod
    async def write(self, entry: Dict[str, Any]) -> str:
        """写入单条日志，返回日志ID"""
        pass
    
    @abstractmethod
    async def write_batch(self, entries: List[Dict[str, Any]]) -> List[str]:
        """批量写入日志，返回日志ID列表"""
        pass
    
    @abstractmethod
    async def query(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        sort_field: str = "timestamp",
        sort_desc: bool = True
    ) -> List[Dict[str, Any]]:
        """查询日志"""
        pass
    
    @abstractmethod
    async def count(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """统计日志数量"""
        pass
    
    @abstractmethod
    async def get_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取单条日志"""
        pass
    
    @abstractmethod
    async def delete(
        self,
        log_type: Optional[str] = None,
        before: Optional[datetime] = None,
        ids: Optional[List[str]] = None
    ) -> int:
        """删除日志，返回删除数量"""
        pass
    
    async def stream_query(
        self,
        batch_size: int = 1000,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式查询日志（用于大量数据导出）"""
        offset = 0
        while True:
            batch = await self.query(limit=batch_size, offset=offset, **kwargs)
            if not batch:
                break
            for doc in batch:
                yield doc
            offset += batch_size
            if len(batch) < batch_size:
                break


class MongoLogStorage(LogStorage):
    """MongoDB 日志存储实现"""
    
    def __init__(self, collection_name: str = "system_logs"):
        self.collection_name = collection_name
        self._collection = None
    
    def _get_collection(self):
        """获取 MongoDB 集合（延迟加载）"""
        if self._collection is None:
            self._collection = get_mongo_db()[self.collection_name]
        return self._collection
    
    async def write(self, entry: Dict[str, Any]) -> str:
        """写入单条日志"""
        try:
            # 确保时间戳存在
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.utcnow()
            if "created_at" not in entry:
                entry["created_at"] = datetime.utcnow()
            
            result = await self._get_collection().insert_one(entry)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"MongoDB写入日志失败: {e}")
            raise
    
    async def write_batch(self, entries: List[Dict[str, Any]]) -> List[str]:
        """批量写入日志"""
        if not entries:
            return []
        
        try:
            # 确保所有条目有时间戳
            now = datetime.utcnow()
            for entry in entries:
                if "timestamp" not in entry:
                    entry["timestamp"] = now
                if "created_at" not in entry:
                    entry["created_at"] = now
            
            result = await self._get_collection().insert_many(entries, ordered=False)
            return [str(id) for id in result.inserted_ids]
        except Exception as e:
            logger.error(f"MongoDB批量写入日志失败: {e}")
            raise
    
    async def query(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        sort_field: str = "timestamp",
        sort_desc: bool = True
    ) -> List[Dict[str, Any]]:
        """查询日志"""
        try:
            # 构建查询条件
            filter_query = {}
            
            if log_type:
                filter_query["log_type"] = log_type
            if level:
                filter_query["level"] = level
            if user_id:
                filter_query["user_id"] = user_id
            if tags:
                filter_query["tags"] = {"$in": tags}
            
            # 时间范围
            if start_time or end_time:
                time_filter = {}
                if start_time:
                    time_filter["$gte"] = start_time
                if end_time:
                    time_filter["$lte"] = end_time
                filter_query["timestamp"] = time_filter
            
            # 排序
            sort_order = -1 if sort_desc else 1
            
            # 执行查询
            cursor = self._get_collection().find(filter_query)
            cursor = cursor.sort(sort_field, sort_order).skip(offset).limit(limit)
            
            results = []
            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error(f"MongoDB查询日志失败: {e}")
            raise
    
    async def count(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """统计日志数量"""
        try:
            filter_query = {}
            
            if log_type:
                filter_query["log_type"] = log_type
            if level:
                filter_query["level"] = level
            if user_id:
                filter_query["user_id"] = user_id
            if tags:
                filter_query["tags"] = {"$in": tags}
            
            if start_time or end_time:
                time_filter = {}
                if start_time:
                    time_filter["$gte"] = start_time
                if end_time:
                    time_filter["$lte"] = end_time
                filter_query["timestamp"] = time_filter
            
            return await self._get_collection().count_documents(filter_query)
            
        except Exception as e:
            logger.error(f"MongoDB统计日志失败: {e}")
            raise
    
    async def get_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取单条日志"""
        try:
            doc = await self._get_collection().find_one({"_id": ObjectId(log_id)})
            if doc:
                doc["id"] = str(doc.pop("_id"))
            return doc
        except Exception as e:
            logger.error(f"MongoDB获取日志详情失败: {e}")
            return None
    
    async def delete(
        self,
        log_type: Optional[str] = None,
        before: Optional[datetime] = None,
        ids: Optional[List[str]] = None
    ) -> int:
        """删除日志"""
        try:
            filter_query = {}
            
            if ids:
                filter_query["_id"] = {"$in": [ObjectId(id) for id in ids]}
            else:
                if log_type:
                    filter_query["log_type"] = log_type
                if before:
                    filter_query["timestamp"] = {"$lt": before}
            
            result = await self._get_collection().delete_many(filter_query)
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"MongoDB删除日志失败: {e}")
            raise
    
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行聚合查询"""
        try:
            cursor = self._get_collection().aggregate(pipeline)
            return [doc async for doc in cursor]
        except Exception as e:
            logger.error(f"MongoDB聚合查询失败: {e}")
            raise


class FileLogStorage(LogStorage):
    """文件日志存储实现（用于归档）"""
    
    def __init__(self, base_path: str = "logs/archive"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
    
    def _get_file_path(self, date: Optional[datetime] = None, log_type: Optional[str] = None) -> Path:
        """获取日志文件路径，按日期和类型分目录"""
        now = date or datetime.utcnow()
        type_dir = log_type or "mixed"
        
        path = self.base_path / type_dir / now.strftime("%Y/%m")
        path.mkdir(parents=True, exist_ok=True)
        
        return path / f"{now.strftime('%Y-%m-%d')}.jsonl"
    
    async def write(self, entry: Dict[str, Any]) -> str:
        """写入单条日志"""
        file_path = self._get_file_path(
            date=entry.get("timestamp"),
            log_type=entry.get("log_type")
        )
        
        async with self._lock:
            async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
                await f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
        
        return str(file_path)
    
    async def write_batch(self, entries: List[Dict[str, Any]]) -> List[str]:
        """批量写入日志（按日期分组）"""
        if not entries:
            return []
        
        # 按文件路径分组
        groups: Dict[Path, List[Dict]] = {}
        for entry in entries:
            path = self._get_file_path(
                date=entry.get("timestamp"),
                log_type=entry.get("log_type")
            )
            groups.setdefault(path, []).append(entry)
        
        results = []
        async with self._lock:
            for path, group_entries in groups.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(path, mode='a', encoding='utf-8') as f:
                    for entry in group_entries:
                        await f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
                        results.append(str(path))
        
        return results
    
    async def query(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """从文件查询日志（性能有限，建议仅用于归档查询）"""
        results = []
        skipped = 0
        
        # 确定要扫描的日期范围
        start_date = start_time or datetime.utcnow() - timedelta(days=30)
        end_date = end_time or datetime.utcnow()
        
        current_date = end_date
        while current_date >= start_date and len(results) < limit:
            file_path = self._get_file_path(date=current_date, log_type=log_type)
            
            if file_path.exists():
                try:
                    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                        async for line in f:
                            if not line.strip():
                                continue
                            
                            try:
                                entry = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            
                            # 过滤条件
                            if level and entry.get("level") != level:
                                continue
                            if user_id and entry.get("user_id") != user_id:
                                continue
                            if tags and not any(tag in entry.get("tags", []) for tag in tags):
                                continue
                            
                            if skipped < offset:
                                skipped += 1
                                continue
                            
                            results.append(entry)
                            
                            if len(results) >= limit:
                                break
                                
                except Exception as e:
                    logger.error(f"读取日志文件失败 {file_path}: {e}")
            
            current_date -= timedelta(days=1)
        
        return results
    
    async def count(self, **kwargs) -> int:
        """统计日志数量"""
        # 文件存储不高效支持count，返回估算值
        return -1
    
    async def get_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取单条日志（文件存储不支持ID查询）"""
        return None
    
    async def delete(self, **kwargs) -> int:
        """删除日志（文件存储不支持删除）"""
        return 0


class MemoryLogStorage(LogStorage):
    """内存日志存储实现（用于测试和临时缓存）"""
    
    def __init__(self, max_size: int = 10000):
        self._logs: List[Dict[str, Any]] = []
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._counter = 0
    
    async def write(self, entry: Dict[str, Any]) -> str:
        """写入单条日志"""
        async with self._lock:
            self._counter += 1
            entry["id"] = f"mem_{self._counter}"
            self._logs.append(entry)
            
            # 限制大小
            if len(self._logs) > self._max_size:
                self._logs = self._logs[-self._max_size:]
            
            return entry["id"]
    
    async def write_batch(self, entries: List[Dict[str, Any]]) -> List[str]:
        """批量写入日志"""
        ids = []
        for entry in entries:
            id = await self.write(entry)
            ids.append(id)
        return ids
    
    async def query(
        self,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        sort_desc: bool = True,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """查询日志"""
        async with self._lock:
            results = []
            
            for entry in self._logs:
                # 过滤条件
                if log_type and entry.get("log_type") != log_type:
                    continue
                if level and entry.get("level") != level:
                    continue
                if user_id and entry.get("user_id") != user_id:
                    continue
                if tags and not any(tag in entry.get("tags", []) for tag in tags):
                    continue
                
                # 时间范围
                entry_time = entry.get("timestamp")
                if entry_time:
                    if start_time and entry_time < start_time:
                        continue
                    if end_time and entry_time > end_time:
                        continue
                
                results.append(entry)
            
            # 排序
            results.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=sort_desc)
            
            # 分页
            return results[offset:offset + limit]
    
    async def count(self, **kwargs) -> int:
        """统计日志数量"""
        results = await self.query(limit=self._max_size, **kwargs)
        return len(results)
    
    async def get_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取单条日志"""
        async with self._lock:
            for entry in self._logs:
                if entry.get("id") == log_id:
                    return entry.copy()
            return None
    
    async def delete(
        self,
        log_type: Optional[str] = None,
        before: Optional[datetime] = None,
        ids: Optional[List[str]] = None,
        **kwargs
    ) -> int:
        """删除日志"""
        async with self._lock:
            original_len = len(self._logs)
            
            if ids:
                self._logs = [e for e in self._logs if e.get("id") not in ids]
            else:
                new_logs = []
                for entry in self._logs:
                    if log_type and entry.get("log_type") == log_type:
                        continue
                    if before:
                        entry_time = entry.get("timestamp")
                        if entry_time and entry_time < before:
                            continue
                    new_logs.append(entry)
                self._logs = new_logs
            
            return original_len - len(self._logs)
    
    def clear(self):
        """清空所有日志"""
        self._logs.clear()


# 全局存储实例缓存
_storage_instances: Dict[str, LogStorage] = {}


def get_storage_instance(
    storage_type: str = "mongodb",
    **kwargs
) -> LogStorage:
    """获取存储实例（单例模式）"""
    global _storage_instances
    
    key = f"{storage_type}:{str(kwargs)}"
    
    if key not in _storage_instances:
        if storage_type == "mongodb":
            _storage_instances[key] = MongoLogStorage(**kwargs)
        elif storage_type == "file":
            _storage_instances[key] = FileLogStorage(**kwargs)
        elif storage_type == "memory":
            _storage_instances[key] = MemoryLogStorage(**kwargs)
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
    
    return _storage_instances[key]


def reset_storage_instances():
    """重置所有存储实例（测试用）"""
    global _storage_instances
    _storage_instances.clear()
