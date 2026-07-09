"""
调仓模块数据模型。

定义调仓动作、调仓方案、候选股票池、当前组合等核心数据结构，
并提供与 JSON / dict 之间的序列化辅助方法。
"""

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Mapping, Optional
from typing import Literal

import pandas as pd

from recommender.portfolio_advisor.dimension.run import PortfolioDimensions, compute_portfolio_dimensions


@dataclass(frozen=True)
class RebalanceAction:
    """一次调仓动作。"""

    action_type: Literal["remove", "add", "replace", "adjust_weight"]
    code_out: Optional[str] = None
    code_in: Optional[str] = None
    weight_out: float = 0.0
    weight_in: float = 0.0
    reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_type,
            "code_out": self.code_out,
            "code_in": self.code_in,
            "weight_out": self.weight_out,
            "weight_in": self.weight_in,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RebalancePlan:
    """一套完整调仓方案，包含调仓前后得分对比。"""

    actions: List[RebalanceAction]
    portfolio_before: PortfolioDimensions
    portfolio_after: PortfolioDimensions
    score_before: float
    score_after: float
    improvement: float
    objective: str

    def to_dict(self) -> Dict:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "score_before": self.score_before,
            "score_after": self.score_after,
            "improvement": self.improvement,
            "objective": self.objective,
            "dimensions_before": dict(self.portfolio_before.to_score_dict()),
            "dimensions_after": dict(self.portfolio_after.to_score_dict()),
        }


@dataclass
class StockCandidate:
    """候选股票，用于调仓搜索。"""

    code: str
    df: Optional[pd.DataFrame] = None
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    industry: Optional[str] = None

    def to_dict(self) -> Dict:
        start_date = end_date = None
        if self.df is not None and "date" in self.df.columns:
            start_date = str(self.df["date"].iloc[0])
            end_date = str(self.df["date"].iloc[-1])
        return {
            "code": self.code,
            "start_date": start_date,
            "end_date": end_date,
            "dimension_scores": dict(self.dimension_scores),
            "industry": self.industry,
        }


@dataclass
class CandidatePool:
    """候选股票池。"""

    candidates: List[StockCandidate] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.candidates)

    def __iter__(self):
        return iter(self.candidates)

    def to_dict(self) -> Dict:
        return {"candidates": [c.to_dict() for c in self.candidates]}

    @classmethod
    def from_candidates(cls, candidates: List[StockCandidate]) -> "CandidatePool":
        return cls(candidates=candidates)


@dataclass
class CurrentPortfolio:
    """当前投资组合。"""

    codes: List[str]
    weights: List[float]
    dfs: List[pd.DataFrame]

    def __post_init__(self):
        if len(self.codes) != len(self.weights) or len(self.codes) != len(self.dfs):
            raise ValueError("codes / weights / dfs 长度必须一致")

    def to_dimensions(self) -> PortfolioDimensions:
        return compute_portfolio_dimensions(self.dfs, self.weights)

    def to_dict(self) -> Dict:
        return {
            "codes": list(self.codes),
            "weights": list(self.weights),
            "start_dates": [str(df["date"].iloc[0]) if "date" in df.columns else None for df in self.dfs],
            "end_dates": [str(df["date"].iloc[-1]) if "date" in df.columns else None for df in self.dfs],
        }
