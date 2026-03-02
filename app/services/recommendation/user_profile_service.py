"""
用户画像服务
管理用户推荐偏好设置和推荐历史
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from pymongo import MongoClient

from app.core.db.document import _init_db

logger = logging.getLogger(__name__)


class UserProfileService:
    """
    用户画像服务
    
    负责:
    - 用户推荐偏好的 CRUD
    - 用户推荐历史记录
    - 已推荐股票去重
    """
    
    COLLECTION_NAME = "user_recommendation_preferences"
    HISTORY_COLLECTION = "user_recommendation_history"
    
    def __init__(self):
        client, db = _init_db()
        self.db = db
        self.collection = self.db[self.COLLECTION_NAME]
        self.history_collection = self.db[self.HISTORY_COLLECTION]
        logger.info("UserProfileService 初始化完成")
    
    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像"""
        profile = await self.collection.find_one({"user_id": user_id})
        
        if profile:
            profile["_id"] = str(profile["_id"])
            return profile
        
        return None
    
    async def get_viewed_symbols(self, user_id: str, days: int = 7) -> List[str]:
        """
        获取用户已查看的股票代码列表
        
        Args:
            user_id: 用户ID
            days: 查询最近几天的记录，默认7天
            
        Returns:
            已查看的股票代码列表
        """
        since = datetime.now() - timedelta(days=days)
        
        cursor = self.history_collection.find(
            {
                "user_id": user_id,
                "viewed_at": {"$gte": since}
            },
            {"symbol": 1, "_id": 0}
        )
        
        symbols = [doc["symbol"] async for doc in cursor]
        return list(set(symbols))  # 去重
    
    async def record_view(self, user_id: str, symbol: str, recommendation_date: str):
        """
        记录用户查看推荐
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            recommendation_date: 推荐数据日期
        """
        await self.history_collection.update_one(
            {
                "user_id": user_id,
                "symbol": symbol,
                "recommendation_date": recommendation_date
            },
            {
                "$set": {
                    "viewed_at": datetime.now()
                },
                "$inc": {
                    "view_count": 1
                }
            },
            upsert=True
        )
    
    async def get_recommendation_history(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取用户推荐历史
        
        Args:
            user_id: 用户ID
            skip: 跳过数量
            limit: 返回数量
            
        Returns:
            历史记录列表
        """
        cursor = self.history_collection.find(
            {"user_id": user_id}
        ).sort("viewed_at", -1).skip(skip).limit(limit)
        
        history = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            history.append(doc)
        
        return history
    
    async def clear_history(self, user_id: str) -> bool:
        """
        清空用户推荐历史
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        result = await self.history_collection.delete_many({"user_id": user_id})
        logger.info(f"清空用户 {user_id} 的推荐历史，删除了 {result.deleted_count} 条记录")
        return result.deleted_count > 0


# 单例实例
_user_profile_service: Optional[UserProfileService] = None


def get_user_profile_service() -> UserProfileService:
    """获取用户画像服务实例"""
    global _user_profile_service
    if _user_profile_service is None:
        _user_profile_service = UserProfileService()
    return _user_profile_service
