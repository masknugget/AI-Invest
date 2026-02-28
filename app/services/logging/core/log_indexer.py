"""
日志索引管理
优化 MongoDB 查询性能
"""

from typing import Dict, Any, List, Optional
import logging

from app.services.logging.models import LogType, DEFAULT_LOG_TYPE_CONFIGS

logger = logging.getLogger("webapi")


# 推荐的索引配置
RECOMMENDED_INDEXES: Dict[str, List[List[tuple]]] = {
    LogType.OPERATION: [
        [("timestamp", -1)],
        [("user_id", 1), ("timestamp", -1)],
        [("action_type", 1), ("timestamp", -1)],
        [("success", 1)],
    ],
    LogType.AUDIT: [
        [("timestamp", -1)],
        [("user_id", 1), ("timestamp", -1)],
        [("audit_type", 1), ("timestamp", -1)],
        [("resource_type", 1), ("resource_id", 1)],
    ],
    LogType.ERROR: [
        [("timestamp", -1)],
        [("error_type", 1), ("timestamp", -1)],
        [("is_resolved", 1)],
        [("level", 1)],
    ],
    LogType.ACCESS: [
        [("timestamp", -1)],
        [("user_id", 1), ("timestamp", -1)],
        [("path", 1), ("timestamp", -1)],
        [("status_code", 1)],
    ],
    LogType.BEHAVIOR: [
        [("timestamp", -1)],
        [("user_id", 1), ("timestamp", -1)],
        [("behavior_type", 1)],
    ],
    LogType.SYSTEM: [
        [("timestamp", -1)],
        [("level", 1), ("timestamp", -1)],
        [("component", 1)],
    ],
    LogType.SECURITY: [
        [("timestamp", -1)],
        [("threat_type", 1), ("timestamp", -1)],
        [("severity", 1)],
        [("source_ip", 1)],
    ],
}


class LogIndexer:
    """日志索引管理器"""
    
    def __init__(self, collection_name: str = "system_logs"):
        self.collection_name = collection_name
        self._collection = None
    
    def _get_collection(self):
        """获取 MongoDB 集合"""
        if self._collection is None:
            from app.core.database import get_mongo_db
            self._collection = get_mongo_db()[self.collection_name]
        return self._collection
    
    async def create_indexes(self) -> Dict[str, Any]:
        """创建所有推荐索引"""
        results = {
            "created": [],
            "failed": [],
            "skipped": []
        }
        
        collection = self._get_collection()
        
        # 通用索引（所有日志类型共用）
        common_indexes = [
            [("timestamp", -1)],
            [("user_id", 1)],
            [("level", 1)],
            [("log_type", 1), ("timestamp", -1)],
            [("tags", 1)],
        ]
        
        for index_keys in common_indexes:
            try:
                await collection.create_index(index_keys, background=True)
                results["created"].append(f"common: {index_keys}")
            except Exception as e:
                logger.warning(f"创建索引失败 {index_keys}: {e}")
                results["failed"].append(f"common: {index_keys} - {e}")
        
        logger.info(f"索引创建完成: 成功={len(results['created'])}, 失败={len(results['failed'])}")
        return results
    
    async def drop_indexes(self) -> Dict[str, Any]:
        """删除所有索引（谨慎使用）"""
        results = {
            "dropped": [],
            "failed": []
        }
        
        try:
            collection = self._get_collection()
            
            # 获取现有索引
            existing = await collection.index_information()
            
            for index_name in existing:
                if index_name != "_id_":  # 保留主键索引
                    try:
                        await collection.drop_index(index_name)
                        results["dropped"].append(index_name)
                    except Exception as e:
                        results["failed"].append(f"{index_name}: {e}")
            
            logger.info(f"索引删除完成: 成功={len(results['dropped'])}, 失败={len(results['failed'])}")
            
        except Exception as e:
            logger.error(f"删除索引失败: {e}")
            results["failed"].append(str(e))
        
        return results
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            collection = self._get_collection()
            
            # 索引信息
            indexes = await collection.index_information()
            
            # 集合统计
            stats = await collection.database.command("collStats", self.collection_name)
            
            return {
                "indexes": [
                    {
                        "name": name,
                        "keys": info.get("key", {}),
                        "unique": info.get("unique", False),
                        "background": info.get("background", False)
                    }
                    for name, info in indexes.items()
                ],
                "total_index_size_mb": round(stats.get("totalIndexSize", 0) / (1024 * 1024), 2),
                "index_count": len(indexes)
            }
            
        except Exception as e:
            logger.error(f"获取索引统计失败: {e}")
            return {"error": str(e)}


class IndexManager:
    """索引管理工具"""
    
    @staticmethod
    async def optimize_query(
        log_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        level: Optional[str] = None
    ) -> List[tuple]:
        """
        根据查询条件推荐最优索引
        
        Returns:
            推荐的索引键列表
        """
        recommended = []
        
        # 等值查询优先
        if log_type:
            recommended.append(("log_type", 1))
        if user_id:
            recommended.append(("user_id", 1))
        if level:
            recommended.append(("level", 1))
        
        # 范围查询放最后
        if start_time or end_time:
            recommended.append(("timestamp", -1))
        
        return recommended if recommended else [("timestamp", -1)]
    
    @staticmethod
    def get_index_usage_report(index_stats: Dict[str, Any]) -> Dict[str, Any]:
        """分析索引使用情况并给出优化建议"""
        report = {
            "total_indexes": 0,
            "total_size_mb": 0,
            "recommendations": []
        }
        
        if "indexes" in index_stats:
            report["total_indexes"] = len(index_stats["indexes"])
        
        if "total_index_size_mb" in index_stats:
            report["total_size_mb"] = index_stats["total_index_size_mb"]
        
        # 优化建议
        if report["total_indexes"] > 10:
            report["recommendations"].append(
                "索引数量较多，建议定期清理未使用的索引以减少写入开销"
            )
        
        if report["total_size_mb"] > 1000:
            report["recommendations"].append(
                "索引占用空间超过1GB，建议归档旧数据或重建索引"
            )
        
        return report
