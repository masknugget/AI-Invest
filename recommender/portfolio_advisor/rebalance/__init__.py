"""
投资组合调仓建议模块。

按功能拆分为多个子模块：
- types: 数据模型
- scoring: 目标函数评分
- weights: 权重再分配策略
- constraints: 约束校验
- plan_builder: 调仓方案构造
- search: 组合搜索
- loader: 候选池加载
- engine: 对外主入口 suggest_rebalance

提供个股调入/调出建议，支持启发式筛选与全量重算验证。
"""

from research.portfolio_advisor.rebalance import (
    constraints,
    loader,
    plan_builder,
    scoring,
    search,
    types,
    weights,
)
from research.portfolio_advisor.rebalance.engine import suggest_rebalance
from research.portfolio_advisor.rebalance.loader import (
    load_candidate_pool_from_jsonl,
    load_candidate_pool_from_jsonl_as_pool,
)
from research.portfolio_advisor.rebalance.scoring import (
    OBJECTIVES,
    evaluate_portfolio,
    extract_objective_score,
)
from research.portfolio_advisor.rebalance.types import (
    CandidatePool,
    CurrentPortfolio,
    RebalanceAction,
    RebalancePlan,
    StockCandidate,
)
from research.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES, replace_stock

__all__ = [
    "suggest_rebalance",
    "load_candidate_pool_from_jsonl",
    "load_candidate_pool_from_jsonl_as_pool",
    "replace_stock",
    "evaluate_portfolio",
    "extract_objective_score",
    "CandidatePool",
    "CurrentPortfolio",
    "RebalanceAction",
    "RebalancePlan",
    "StockCandidate",
    "OBJECTIVES",
    "WEIGHT_STRATEGIES",
    "types",
    "scoring",
    "weights",
    "constraints",
    "plan_builder",
    "search",
    "loader",
]

