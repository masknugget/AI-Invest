"""
应用层推荐服务 - 简化版

封装 recommender 模块，提供业务逻辑
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from pymongo import MongoClient

from app.core.config import settings
from app.models.recommendation import (
    RecommendationQuery,
    StockRecommendationResponse,
    RecommendationListResponse,
    RecommendationStats,
    DashboardData,
    HotStock,
    RiskLevel,
    InvestmentStyle,
    StockMetrics,
    RecommendationReasons,
)
from .user_profile_service import get_user_profile_service

logger = logging.getLogger(__name__)


class RecommendationAppService:
    """
    应用层推荐服务
    
    职责:
    - 封装 recommender 模块的核心功能
    - 处理 API 层业务逻辑
    - 数据转换和格式化
    """
    
    def __init__(self):
        # 初始化 MongoDB 连接
        self.client = MongoClient(settings.MONGODB_URI)
        self.db = self.client[settings.MONGODB_DB]
        self.rec_collection = self.db["daily_stock_recommendations"]
        logger.info("RecommendationAppService 初始化完成")
    
    async def get_recommendations_by_filter(
        self,
        query: RecommendationQuery,
        user_id: Optional[str] = None
    ) -> RecommendationListResponse:
        """
        根据条件筛选推荐
        
        Args:
            query: 查询参数
            user_id: 用户ID，用于去重
            
        Returns:
            推荐列表响应
        """
        date = query.date or self._get_latest_date()
        
        if date is None:
            return RecommendationListResponse(date="", total=0, recommendations=[], has_more=False)
        
        # 构建查询条件
        filter_dict = {"analysis_date": date}
        
        if query.risk_level:
            filter_dict["risk_level"] = query.risk_level.value
        
        if query.min_score:
            filter_dict["overall_score"] = {"$gte": query.min_score}
        
        if query.industries:
            filter_dict["industry"] = {"$in": query.industries}
        
        # 如果需要排除已查看的，获取已查看列表
        if query.exclude_viewed and user_id:
            profile_service = get_user_profile_service()
            viewed_symbols = await profile_service.get_viewed_symbols(user_id, days=30)
            if viewed_symbols:
                filter_dict["symbol"] = {"$nin": viewed_symbols}
        
        # 先获取总数
        total = self.rec_collection.count_documents(filter_dict)
        
        # 查询数据（支持分页）
        cursor = self.rec_collection.find(
            filter_dict,
            {"_id": 0}
        ).sort("overall_score", -1).skip(query.skip).limit(query.top_k)
        
        recommendations = [self._to_stock_response(doc) for doc in cursor]
        
        # 判断是否还有更多
        has_more = (query.skip + len(recommendations)) < total
        
        return RecommendationListResponse(
            date=date,
            total=len(recommendations),
            recommendations=recommendations,
            has_more=has_more,
            skip=query.skip,
        )
    
    async def get_stock_recommendation(
        self,
        symbol: str,
        date: Optional[str] = None
    ) -> Optional[StockRecommendationResponse]:
        """
        获取单只股票的推荐详情
        
        Args:
            symbol: 股票代码
            date: 日期，默认最新
            
        Returns:
            股票推荐详情
        """
        if date is None:
            date = self._get_latest_date()
        
        if date is None:
            return None
        
        stock_data = self.rec_collection.find_one(
            {"symbol": symbol, "analysis_date": date},
            {"_id": 0}
        )
        
        if not stock_data:
            return None
        
        return self._to_stock_response(stock_data)
    
    async def get_stats(self, date: Optional[str] = None) -> Optional[RecommendationStats]:
        """
        获取推荐统计
        
        Args:
            date: 日期，默认最新
            
        Returns:
            统计数据
        """
        from recommender.recommendation_service import RecommendationService
        
        rec_service = RecommendationService()
        stats = rec_service.get_stats(date)
        
        if "error" in stats:
            return None
        
        return RecommendationStats(
            date=stats["date"],
            total_stocks=stats["total_stocks"],
            recommendation_distribution=stats["recommendation_distribution"],
            risk_distribution=stats["risk_distribution"],
            style_distribution={},  # TODO: 计算风格分布
        )
    
    async def get_dashboard_data(self) -> Optional[DashboardData]:
        """
        获取仪表盘数据
        
        Returns:
            仪表盘数据
        """
        date = self._get_latest_date()
        if date is None:
            return None
        
        # 获取统计数据
        stats = await self.get_stats(date)
        if stats is None:
            return None
        
        # 获取热门股票（评分最高的几只）
        cursor = self.rec_collection.find(
            {"analysis_date": date, "overall_score": {"$gte": 80}},
            {"_id": 0}
        ).sort("overall_score", -1).limit(5)
        
        hot_stocks = []
        for doc in cursor:
            hot_stocks.append(HotStock(
                symbol=doc["symbol"],
                name=doc.get("name", ""),
                industry=doc.get("industry", ""),
                overall_score=doc.get("overall_score", 0),
                recommendation=doc.get("recommendation", "持有"),
                trend="up" if doc.get("overall_score", 0) >= 80 else "flat",
            ))
        
        return DashboardData(
            latest_date=date,
            total_stocks=stats.total_stocks,
            hot_stocks=hot_stocks,
            stats=stats,
        )
    
    async def trigger_batch_generation(
        self,
        max_stocks: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        触发批量生成（管理功能）
        
        Args:
            max_stocks: 最大处理数量
            
        Returns:
            生成结果
        """
        from recommender import run_daily_batch
        
        logger.info(f"手动触发批处理生成，max_stocks={max_stocks}")
        
        result = run_daily_batch(max_stocks=max_stocks)
        
        return {
            "date": result.get("date"),
            "total_stocks": result.get("total_stocks"),
            "processed": result.get("processed"),
            "status": result.get("status"),
            "message": "批处理完成" if result.get("status") == "success" else "批处理失败",
        }
    
    def _get_latest_date(self) -> Optional[str]:
        """获取最新的推荐日期"""
        try:
            doc = self.rec_collection.find_one(
                {},
                sort=[("analysis_date", -1)],
                projection={"analysis_date": 1}
            )
            return doc.get("analysis_date") if doc else None
        except Exception as e:
            logger.error(f"获取最新日期失败: {e}")
            return None
    
    def _to_stock_response(
        self,
        stock_data: Dict[str, Any]
    ) -> StockRecommendationResponse:
        """
        转换为响应模型
        
        Args:
            stock_data: 股票推荐数据
            
        Returns:
            StockRecommendationResponse
        """
        # 处理 suitable_for 字段
        suitable_for = stock_data.get("suitable_for", [])
        if suitable_for and isinstance(suitable_for[0], str):
            suitable_for = [InvestmentStyle(s) for s in suitable_for if s in [e.value for e in InvestmentStyle]]
        
        return StockRecommendationResponse(
            symbol=stock_data["symbol"],
            name=stock_data.get("name", ""),
            industry=stock_data.get("industry", ""),
            metrics=StockMetrics(
                pe=stock_data.get("pe"),
                pb=stock_data.get("pb"),
                roe=stock_data.get("roe"),
                dividend_yield=stock_data.get("dividend_yield"),
            ),
            overall_score=stock_data.get("overall_score", 0),
            recommendation=stock_data.get("recommendation", "持有"),
            risk_level=RiskLevel(stock_data.get("risk_level", "中")),
            suitable_for=suitable_for,
            reasons=RecommendationReasons(
                general=stock_data.get("reason", ""),
                for_value=stock_data.get("reason_for_value", ""),
                for_growth=stock_data.get("reason_for_growth", ""),
                for_dividend=stock_data.get("reason_for_dividend", ""),
            ),
            analysis_date=stock_data.get("analysis_date", ""),
            updated_at=stock_data.get("updated_at"),
        )


# 单例实例
_recommendation_service: Optional[RecommendationAppService] = None


def get_recommendation_service() -> RecommendationAppService:
    """获取推荐服务实例"""
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationAppService()
    return _recommendation_service
