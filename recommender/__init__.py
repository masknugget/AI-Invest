"""
股票推荐系统 - 离线批处理 + 在线匹配架构

架构:
1. 离线层 (batch_generator.py)
   - 每天定时运行
   - 为所有股票调用LLM生成推荐数据
   - 存储到MongoDB

2. 在线层 (recommendation_service.py)
   - 从预计算数据中快速匹配
   - 根据用户画像筛选排序
   - 毫秒级响应

Usage:
    # 离线：每日批处理 (定时任务或脚本)
    from recommender import run_daily_batch
    run_daily_batch()  # 生成当日所有股票推荐

    # 在线：为用户推荐
    from recommender import RecommendationService, UserProfile
    
    service = RecommendationService()
    user = UserProfile(user_id="user_001", risk_level="中")
    recommendations = service.recommend(user, top_k=5)
    
    for rec in recommendations:
        print(f"{rec.name}: {rec.reason}")

快速推荐:
    from recommender import quick_recommend
    recommendations = quick_recommend(
        user_id="user_001",
        risk_level="稳健型",
        preferred_styles=["价值投资", "股息投资"],
        top_k=5
    )
"""

from recommender.models import (
    UserProfile,
    UserRecommendation,
    StockRecommendation,
    RiskLevel,
    InvestmentStyle,
)

from recommender.batch_generator import (
    run_daily_batch,
    generate_daily_recommendations,
    process_batch,
    get_stocks_by_symbols,
)

from recommender.recommendation_service import (
    RecommendationService,
    quick_recommend,
)

from recommender.engine import (
    SimpleRecommender,
    recommend_for_user,
    StockBrief,
    Recommendation,
)

__all__ = [
    # 模型
    "UserProfile",
    "UserRecommendation",
    "StockRecommendation",
    "RiskLevel",
    "InvestmentStyle",
    
    # 离线批处理
    "run_daily_batch",
    "generate_daily_recommendations",
    "process_batch",
    "get_stocks_by_symbols",
    
    # 在线服务
    "RecommendationService",
    "quick_recommend",
    
    # 简化推荐引擎
    "SimpleRecommender",
    "recommend_for_user",
    "StockBrief",
    "Recommendation",
]

__version__ = "1.0.0"
