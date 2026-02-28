"""
在线推荐服务
从预计算的每日推荐数据中快速匹配用户偏好
"""

import logging
from typing import List, Optional
from datetime import datetime

from pymongo import MongoClient

from recommender.models import UserProfile, UserRecommendation, StockRecommendation

logger = logging.getLogger(__name__)

# MongoDB 配置
MONGO_URI = "mongodb://localhost:27017"
REC_DB = "recommendations"
REC_COLLECTION = "daily_stock_recommendations"


class RecommendationService:
    """
    在线推荐服务
    
    特点:
    - 从预计算数据中查询，不调用LLM
    - 毫秒级响应
    - 根据用户画像实时匹配
    """
    
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[REC_DB]
        self.collection = self.db[REC_COLLECTION]
        logger.info("RecommendationService 初始化完成")
    
    def recommend(
        self,
        user: UserProfile,
        top_k: int = 5,
        date: str = None
    ) -> List[UserRecommendation]:
        """
        为用户推荐股票
        
        Args:
            user: 用户画像
            top_k: 推荐数量
            date: 指定日期 (默认今天)
            
        Returns:
            推荐列表
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"为用户 {user.user_id} 推荐 (日期: {date})")
        
        # 1. 获取当日预计算推荐数据
        candidates = self._get_daily_recommendations(date)
        if not candidates:
            logger.warning(f"没有找到 {date} 的推荐数据")
            return []
        
        logger.info(f"获取到 {len(candidates)} 只候选股票")
        
        # 2. 根据用户画像筛选和排序
        matched = self._match_user_preference(candidates, user)
        
        # 3. 组装最终结果
        recommendations = self._assemble_recommendations(matched, user, top_k)
        
        logger.info(f"返回 {len(recommendations)} 条推荐")
        return recommendations
    
    def _get_daily_recommendations(
        self,
        date: str
    ) -> List[StockRecommendation]:
        """从MongoDB获取当日推荐数据"""
        try:
            cursor = self.collection.find(
                {"analysis_date": date},
                {"_id": 0}
            ).sort("overall_score", -1)
            
            recommendations = []
            for doc in cursor:
                rec = StockRecommendation(
                    symbol=doc["symbol"],
                    name=doc["name"],
                    industry=doc.get("industry", ""),
                    pe=doc.get("pe"),
                    pb=doc.get("pb"),
                    roe=doc.get("roe"),
                    dividend_yield=doc.get("dividend_yield"),
                    overall_score=doc.get("overall_score", 0),
                    recommendation=doc.get("recommendation", "持有"),
                    risk_level=doc.get("risk_level", "中"),
                    suitable_for=doc.get("suitable_for", []),
                    reason_for_value=doc.get("reason_for_value", ""),
                    reason_for_growth=doc.get("reason_for_growth", ""),
                    reason_for_dividend=doc.get("reason_for_dividend", ""),
                    analysis_date=date,
                )
                recommendations.append(rec)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"获取推荐数据失败: {e}")
            return []
    
    def _match_user_preference(
        self,
        candidates: List[StockRecommendation],
        user: UserProfile
    ) -> List[tuple]:
        """
        根据用户画像匹配股票
        
        返回: [(股票, 匹配分数, 匹配原因)]
        """
        matched = []
        
        for stock in candidates:
            score = 0.0
            reasons = []
            
            # 1. 基础分数 (预计算的overall_score占50%)
            score += stock.overall_score * 0.5
            
            # 2. 投资风格匹配 (30%)
            if user.preferred_styles:
                style_match = set(stock.suitable_for) & set(user.preferred_styles)
                if style_match:
                    score += 30
                    reasons.append(f"符合{list(style_match)[0]}风格")
                else:
                    score -= 10  # 风格不匹配扣分
            else:
                score += 15  # 用户没指定风格，给中等分
            
            # 3. 风险等级匹配 (10%)
            risk_map = {"低": 1, "中": 2, "高": 3}
            user_risk = risk_map.get(user.risk_level, 2)
            stock_risk = risk_map.get(stock.risk_level, 2)
            
            if stock_risk <= user_risk:
                score += 10
            else:
                score -= 20  # 风险过高严重扣分
                reasons.append(f"风险等级({stock.risk_level})高于用户承受力")
            
            # 4. 行业偏好 (10%)
            if user.preferred_industries:
                if stock.industry in user.preferred_industries:
                    score += 10
                    reasons.append(f"偏好行业: {stock.industry}")
            else:
                score += 5
            
            # 5. 硬条件过滤
            if user.max_pe is not None and stock.pe is not None:
                if stock.pe > user.max_pe:
                    continue  # 跳过PE过高的
            
            if user.min_dividend_yield is not None and stock.dividend_yield is not None:
                if stock.dividend_yield < user.min_dividend_yield:
                    continue  # 跳过股息率过低的
            
            match_reason = "; ".join(reasons) if reasons else "综合评分优秀"
            matched.append((stock, score, match_reason))
        
        # 按匹配分数排序
        matched.sort(key=lambda x: x[1], reverse=True)
        return matched
    
    def _assemble_recommendations(
        self,
        matched: List[tuple],
        user: UserProfile,
        top_k: int
    ) -> List[UserRecommendation]:
        """组装最终推荐结果"""
        
        recommendations = []
        
        for stock, match_score, match_reason in matched[:top_k]:
            # 根据用户画像选择最佳理由
            reason = self._select_best_reason(stock, user)
            
            # 生成匹配标签
            tags = stock.suitable_for.copy()
            if stock.industry:
                tags.append(stock.industry)
            if stock.risk_level:
                tags.append(f"{stock.risk_level}风险")
            
            rec = UserRecommendation(
                symbol=stock.symbol,
                name=stock.name,
                industry=stock.industry,
                score=match_score,
                reason=reason,
                risk_level=stock.risk_level,
                recommendation=stock.recommendation,
                tags=list(set(tags))[:5],  # 去重，最多5个
                match_reason=match_reason
            )
            recommendations.append(rec)
        
        return recommendations
    
    def _select_best_reason(
        self,
        stock: StockRecommendation,
        user: UserProfile
    ) -> str:
        """根据用户画像选择最佳推荐理由"""
        
        # 优先选择用户偏好风格对应的理由
        if user.preferred_styles:
            for style in user.preferred_styles:
                if style == "价值投资" and stock.reason_for_value:
                    return stock.reason_for_value
                elif style == "成长投资" and stock.reason_for_growth:
                    return stock.reason_for_growth
                elif style == "股息投资" and stock.reason_for_dividend:
                    return stock.reason_for_dividend
        
        # 默认返回非空的理由
        for reason in [stock.reason_for_value, stock.reason_for_growth, stock.reason_for_dividend]:
            if reason:
                return reason
        
        return "综合评分优秀，值得关注"
    
    def get_latest_date(self) -> Optional[str]:
        """获取最新的推荐数据日期"""
        try:
            doc = self.collection.find_one(
                {},
                sort=[("analysis_date", -1)],
                projection={"analysis_date": 1}
            )
            return doc.get("analysis_date") if doc else None
        except Exception as e:
            logger.error(f"获取最新日期失败: {e}")
            return None
    
    def get_stats(self, date: str = None) -> dict:
        """获取推荐数据统计"""
        if date is None:
            date = self.get_latest_date()
        
        if not date:
            return {"error": "没有推荐数据"}
        
        try:
            total = self.collection.count_documents({"analysis_date": date})
            
            # 各推荐等级数量
            pipeline = [
                {"$match": {"analysis_date": date}},
                {"$group": {"_id": "$recommendation", "count": {"$sum": 1}}}
            ]
            rec_counts = list(self.collection.aggregate(pipeline))
            
            # 各风险等级数量
            pipeline = [
                {"$match": {"analysis_date": date}},
                {"$group": {"_id": "$risk_level", "count": {"$sum": 1}}}
            ]
            risk_counts = list(self.collection.aggregate(pipeline))
            
            return {
                "date": date,
                "total_stocks": total,
                "recommendation_distribution": {r["_id"]: r["count"] for r in rec_counts},
                "risk_distribution": {r["_id"]: r["count"] for r in risk_counts},
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"error": str(e)}


# 便捷函数
def quick_recommend(
    user_id: str,
    risk_level: str = "中",
    preferred_styles: List[str] = None,
    preferred_industries: List[str] = None,
    top_k: int = 5
) -> List[UserRecommendation]:
    """
    快速推荐便捷函数
    
    Args:
        user_id: 用户ID
        risk_level: 风险等级 (低/中/高)
        preferred_styles: 偏好风格列表 ["价值投资", "成长投资"]
        preferred_industries: 偏好行业列表
        top_k: 推荐数量
    """
    user = UserProfile(
        user_id=user_id,
        risk_level=risk_level,
        preferred_styles=preferred_styles or [],
        preferred_industries=preferred_industries or []
    )
    
    service = RecommendationService()
    return service.recommend(user, top_k=top_k)
