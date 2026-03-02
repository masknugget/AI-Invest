"""
数据模型模块
"""

# 导入股票数据模型
from .stock_models import (
    StockBasicInfoExtended,
    MarketQuotesExtended,
    MarketInfo,
    TechnicalIndicators,
    StockBasicInfoResponse,
    MarketQuotesResponse,
    StockListResponse,
    MarketType,
    ExchangeType,
    CurrencyType,
    StockStatus
)

# 导入推荐系统模型
from .recommendation import (
    RiskLevel,
    InvestmentStyle,
    RecommendationQuery,
    BatchGenerateRequest,
    StockMetrics,
    RecommendationReasons,
    StockRecommendationResponse,
    RecommendationListResponse,
    HotStock,
    DashboardData,
    RecommendationStats,
    UserProfile,
    StockRecommendation,
    UserRecommendation,
    DailyRecommendationBatch,
)

__all__ = [
    # 股票模型
    "StockBasicInfoExtended",
    "MarketQuotesExtended",
    "MarketInfo",
    "TechnicalIndicators",
    "StockBasicInfoResponse",
    "MarketQuotesResponse",
    "StockListResponse",
    "MarketType",
    "ExchangeType",
    "CurrencyType",
    "StockStatus",
    # 推荐模型
    "RiskLevel",
    "InvestmentStyle",
    "RecommendationQuery",
    "BatchGenerateRequest",
    "StockMetrics",
    "RecommendationReasons",
    "StockRecommendationResponse",
    "RecommendationListResponse",
    "HotStock",
    "DashboardData",
    "RecommendationStats",
    "UserProfile",
    "StockRecommendation",
    "UserRecommendation",
    "DailyRecommendationBatch",
]
