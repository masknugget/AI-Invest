"""
调仓工具函数兼容入口。

具体实现已按功能拆分到 scoring / weights / plan_builder 等子模块，
此处保留对外常用接口的快捷导入。
"""

from recommender.portfolio_advisor.rebalance.scoring import (
    OBJECTIVES,
    evaluate_portfolio,
    extract_objective_score,
)
from recommender.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES, replace_stock

__all__ = [
    "OBJECTIVES",
    "WEIGHT_STRATEGIES",
    "evaluate_portfolio",
    "extract_objective_score",
    "replace_stock",
]
