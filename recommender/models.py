"""
推荐系统模型 - 离线批处理架构
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"


class InvestmentStyle(Enum):
    """投资风格标签"""
    VALUE = "价值投资"
    GROWTH = "成长投资"
    DIVIDEND = "股息投资"
    MOMENTUM = "趋势投资"


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    risk_level: str = "中"  # 低/中/高
    preferred_styles: List[str] = field(default_factory=list)  # ["价值投资", "股息投资"]
    preferred_industries: List[str] = field(default_factory=list)
    max_pe: Optional[float] = None
    min_dividend_yield: Optional[float] = None


@dataclass
class StockRecommendation:
    """
    单只股票的预计算推荐数据
    每天由离线任务批量生成
    """
    symbol: str
    name: str
    industry: str
    
    # 基础指标
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    
    # LLM生成的推荐数据
    overall_score: float = 0.0  # 综合评分 0-100
    recommendation: str = "持有"  # 强烈买入/买入/持有/卖出
    risk_level: str = "中"  # 低/中/高
    
    # 适用投资风格标签
    suitable_for: List[str] = field(default_factory=list)  # ["价值投资", "股息投资"]
    
    # 推荐理由（针对不同风格的简短理由）
    reason_for_value: str = ""  # 价值投资理由
    reason_for_growth: str = ""  # 成长投资理由
    reason_for_dividend: str = ""  # 股息投资理由
    
    # 元数据
    analysis_date: str = ""  # 分析日期
    version: str = "1.0"  # 数据版本
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "industry": self.industry,
            "pe": self.pe,
            "pb": self.pb,
            "roe": self.roe,
            "dividend_yield": self.dividend_yield,
            "overall_score": self.overall_score,
            "recommendation": self.recommendation,
            "risk_level": self.risk_level,
            "suitable_for": self.suitable_for,
        }


@dataclass
class UserRecommendation:
    """
    针对特定用户的最终推荐结果
    在线服务实时组装
    """
    symbol: str
    name: str
    industry: str
    score: float
    reason: str  # 根据用户画像选择的最佳理由
    risk_level: str
    recommendation: str
    tags: List[str] = field(default_factory=list)
    match_reason: str = ""  # 为什么适合该用户
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "industry": self.industry,
            "score": round(self.score, 1),
            "reason": self.reason,
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "tags": self.tags,
            "match_reason": self.match_reason,
        }


@dataclass
class DailyRecommendationBatch:
    """每日推荐批次"""
    date: str
    total_stocks: int
    recommendations: List[StockRecommendation]
    generated_at: datetime = field(default_factory=datetime.now)
