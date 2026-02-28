"""
MongoDB 冷数据归档
将旧数据迁移到独立的归档集合
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from app.core.database import get_mongo_db
from .base_archiver import LogArchiver

logger = logging.getLogger("webapi")


class MongoArchiver(LogArchiver):
    """MongoDB 归档器 - 归档到独立集合"""
    
    def __init__(self, archive_collection: str = "system_logs_archive"):
        self.archive_collection = archive_collection
        self._collection = None
    
    def _get_collection(self):
        """获取归档集合"""
        if self._collection is None:
            self._collection = get_mongo_db()[self.archive_collection]
        return self._collection
    
    async def archive_batch(self, logs: List[Dict[str, Any]]) -> int:
        """归档一批日志"""
        if not logs:
            return 0
        
        try:
            # 标记为已归档
            for log in logs:
                log["archived"] = True
                log["archive_date"] = datetime.utcnow()
                # 移除 MongoDB ID 以便重新插入
                log.pop("_id", None)
                log.pop("id", None)
            
            result = await self._get_collection().insert_many(logs, ordered=False)
            
            archived_count = len(result.inserted_ids)
            logger.debug(f"已归档 {archived_count} 条日志到 {self.archive_collection}")
            
            return archived_count
            
        except Exception as e:
            logger.error(f"MongoDB归档失败: {e}")
            raise
    
    async def retrieve(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        log_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """从归档检索日志"""
        try:
            filter_query = {"archived": True}
            
            if log_type:
                filter_query["log_type"] = log_type
            
            if start_time or end_time:
                time_filter = {}
                if start_time:
                    time_filter["$gte"] = start_time
                if end_time:
                    time_filter["$lte"] = end_time
                filter_query["timestamp"] = time_filter
            
            cursor = self._get_collection().find(filter_query).limit(limit)
            
            results = []
            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error(f"检索归档日志失败: {e}")
            return []
    
    async def delete_archive(
        self,
        before: Optional[datetime] = None,
        log_type: Optional[str] = None
    ) -> int:
        """删除归档日志"""
        try:
            filter_query = {"archived": True}
            
            if log_type:
                filter_query["log_type"] = log_type
            
            if before:
                filter_query["timestamp"] = {"$lt": before}
            
            result = await self._get_collection().delete_many(filter_query)
            
            logger.info(f"从归档删除 {result.deleted_count} 条日志")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"删除归档日志失败: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取归档统计"""
        try:
            collection = self._get_collection()
            
            # 总文档数
            total_docs = await collection.count_documents({"archived": True})
            
            # 按类型统计
            pipeline = [
                {"$match": {"archived": True}},
                {"$group": {"_id": "$log_type", "count": {"$sum": 1}}}
            ]
            type_stats = {}
            async for doc in collection.aggregate(pipeline):
                type_stats[doc["_id"]] = doc["count"]
            
            # 集合统计
            stats = await collection.database.command("collStats", self.archive_collection)
            
            return {
                "total_archived": total_docs,
                "by_type": type_stats,
                "collection_size_mb": round(stats.get("size", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
                "index_size_mb": round(stats.get("totalIndexSize", 0) / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"获取归档统计失败: {e}")
            return {"error": str(e)}
    
    async def create_indexes(self):
        """创建归档集合索引"""
        try:
            collection = self._get_collection()
            
            indexes = [
                [("timestamp", -1)],
                [("log_type", 1), ("timestamp", -1)],
                [("archived", 1)],
                [("archive_date", -1)]
            ]
            
            for index in indexes:
                await collection.create_index(index, background=True)
            
            logger.info(f"归档集合索引创建完成: {self.archive_collection}")
            
        except Exception as e:
            logger.error(f"创建归档索引失败: {e}")
