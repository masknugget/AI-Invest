"""
投资组合五维诊断 - 运行入口

输入：5 只标的的日频行情 DataFrame + 组合权重
输出：5 个维度的原始指标 + 0-100 评分 + 综合健康分

五维对应关系：
- drawdown_control       -> 最大回撤 Maximum Drawdown (MDD)        + 控制得分
- portfolio_diversification -> 有效下注数 Effective Number of Bets (ENB) + 分散得分
- position_efficiency    -> 夏普比率 Sharpe Ratio                   + 性价比得分
- return_stability       -> 年化波动率 Annualized Volatility         + 稳定得分
- style_balance          -> 风格赫芬达尔指数 Style HHI              + 均衡得分
"""

from dataclasses import dataclass
from typing import List, Mapping, Optional, Union, cast

import pandas as pd

from recommender.portfolio_advisor.data_read import load_all

from recommender.portfolio_advisor.dimension.drawdown_control import (
    calculate_portfolio_mdd,
    normalize_mdd_to_score,
)
from recommender.portfolio_advisor.dimension.portfolio_diversification import (
    compute_enb_from_dataframes,
    normalize_enb_to_score,
)
from recommender.portfolio_advisor.dimension.position_efficiency import (
    calculate_portfolio_sharpe_ratio,
    normalize_sharpe_to_score,
)
from recommender.portfolio_advisor.dimension.return_stability import (
    calculate_annualized_volatility,
    normalize_volatility_to_score,
)
from recommender.portfolio_advisor.dimension.style_balance import (
    calculate_style_hhi,
    normalize_style_hhi_to_score,
)


# ============================================================================
# Dataclasses
# ============================================================================


@dataclass(frozen=True)
class DrawdownControl:
    """抗回撤能力：最大回撤及其控制得分（越高越好）。"""

    mdd: float
    score: float


@dataclass(frozen=True)
class PortfolioDiversification:
    """资产分散度：有效下注数及其分散得分（越高越好）。"""

    enb_weight_based: float
    enb_risk_based: float
    score: float


@dataclass(frozen=True)
class PositionEfficiency:
    """持仓性价比：夏普比率及其得分（越高越好）。"""

    sharpe_ratio: float
    score: float


@dataclass(frozen=True)
class ReturnStability:
    """收益稳定性：年化波动率及其稳定得分（越高越好）。"""

    annualized_volatility: float
    score: float


@dataclass(frozen=True)
class StyleBalance:
    """风格均衡：风格 HHI 及其均衡得分（越高越好）。"""

    style_hhi: float
    effective_style_num: float
    score: float


@dataclass(frozen=True)
class PortfolioDimensions:
    """五维组合诊断结果。"""

    drawdown_control: DrawdownControl
    portfolio_diversification: PortfolioDiversification
    position_efficiency: PositionEfficiency
    return_stability: ReturnStability
    style_balance: StyleBalance
    composite_score: float
    geometric_composite_score: float
    dimension_weights: Mapping[str, float]

    def to_score_dict(self) -> Mapping[str, float]:
        """将 5 个维度的评分以字典形式返回（越高越好）。"""
        return {
            "drawdown_control": self.drawdown_control.score,
            "portfolio_diversification": self.portfolio_diversification.score,
            "position_efficiency": self.position_efficiency.score,
            "return_stability": self.return_stability.score,
            "style_balance": self.style_balance.score,
        }


# ============================================================================
# 默认维度权重（与 docs/readme.md 中的示例保持一致）
# ============================================================================

DEFAULT_DIMENSION_WEIGHTS: Mapping[str, float] = {
    "return_stability": 0.25,
    "position_efficiency": 0.20,
    "style_balance": 0.15,
    "drawdown_control": 0.20,
    "portfolio_diversification": 0.20,
}

GEOMETRIC_DIMENSION_WEIGHTS: Mapping[str, float] = {
    "drawdown_control": 0.25,
    "return_stability": 0.20,
    "position_efficiency": 0.25,
    "portfolio_diversification": 0.15,
    "style_balance": 0.15,
}


# ============================================================================
# Pure functions：各维度计算
# ============================================================================


def compute_drawdown_control(
    dfs: List[pd.DataFrame],
    weights: List[float],
) -> DrawdownControl:
    """计算抗回撤能力：MDD + 0-100 控制得分。"""
    mdd = calculate_portfolio_mdd(dfs, weights)
    # normalize_mdd_to_score 返回的是风险分（越高越差），这里反转为控制得分（越高越好）
    score = 100.0 - normalize_mdd_to_score(mdd)
    return DrawdownControl(mdd=mdd, score=score)


def compute_portfolio_diversification(
    dfs: List[pd.DataFrame],
    weights: List[float],
) -> PortfolioDiversification:
    """计算资产分散度：ENB + 0-100 分散得分。"""
    metrics = compute_enb_from_dataframes(dfs, weights, enb_type="both")
    enb_weight = float(metrics["enb_weight_based"])
    enb_risk = float(metrics["enb_risk_based"])
    score = normalize_enb_to_score(enb_weight, len(dfs))
    return PortfolioDiversification(
        enb_weight_based=enb_weight,
        enb_risk_based=enb_risk,
        score=score,
    )


def compute_position_efficiency(
    dfs: List[pd.DataFrame],
    weights: List[float],
) -> PositionEfficiency:
    """计算持仓性价比：Sharpe Ratio + 0-100 得分。"""
    sharpe = calculate_portfolio_sharpe_ratio(dfs, weights)
    score = normalize_sharpe_to_score(sharpe)
    return PositionEfficiency(sharpe_ratio=sharpe, score=score)


def compute_return_stability(
    dfs: List[pd.DataFrame],
    weights: List[float],
) -> ReturnStability:
    """计算收益稳定性：年化波动率 + 0-100 稳定得分。"""
    vol = calculate_annualized_volatility(dfs, weights)
    # normalize_volatility_to_score 返回的是风险分（越高越差），这里反转为稳定得分（越高越好）
    score = 100.0 - normalize_volatility_to_score(vol)
    return ReturnStability(annualized_volatility=vol, score=score)


def compute_style_balance(
    dfs: List[pd.DataFrame],
    weights: List[float],
) -> StyleBalance:
    """计算风格均衡：Style HHI + 0-100 均衡得分。"""
    metrics = calculate_style_hhi(dfs, weights)
    hhi = float(cast(Union[float, int], metrics["style_hhi"]))
    eff_styles = float(cast(Union[float, int], metrics["effective_style_num"]))
    n_styles = int(cast(Union[float, int], metrics["total_styles"]))
    score = normalize_style_hhi_to_score(hhi, n_styles)
    return StyleBalance(
        style_hhi=hhi,
        effective_style_num=eff_styles,
        score=score,
    )


def compute_geometric_composite_score(
    scores: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """
    几何加权综合得分。

    对 0-100 分制的维度得分做几何加权平均：
        score_geo = Π (score_i / 100) ^ w_i * 100

    特点：任一维度得分为 0 时，综合得分为 0；对低分项有惩罚效应，
    更能体现“短板决定生存”的投资逻辑。

    参数
    ----------
    scores : Mapping[str, float]
        各维度得分，键为维度名，值为 0-100 之间的浮点数。
    weights : Mapping[str, float]
        各维度权重，键为维度名，值之和应为 1。

    返回
    -------
    float
        几何加权综合得分，范围 [0, 100]。
    """
    total_weight = sum(weights.values())
    if not (0.999 <= total_weight <= 1.001):
        raise ValueError(f"几何加权权重之和应为 1，当前为 {total_weight}")

    missing = set(weights.keys()) - set(scores.keys())
    if missing:
        raise ValueError(f"缺少维度得分: {missing}")

    geo_ratio = 1.0
    for dim, w in weights.items():
        ratio = scores[dim] / 100.0
        if ratio <= 0.0:
            return 0.0
        geo_ratio *= ratio ** w

    return geo_ratio * 100.0


def compute_portfolio_dimensions(
    dfs: List[pd.DataFrame],
    weights: List[float],
    dimension_weights: Optional[Mapping[str, float]] = None,
    geometric_weights: Optional[Mapping[str, float]] = None,
) -> PortfolioDimensions:
    """
    计算投资组合的五维诊断结果与综合健康分。

    参数
    ----------
    dfs : List[pd.DataFrame]
        n 个资产的日频行情 DataFrame，每个至少包含 'date'、'close'、'pctChg' 列。
    weights : List[float]
        各资产权重，长度与 dfs 一致，且加和为 1。
    dimension_weights : Optional[Mapping[str, float]], default None
        五维在算术加权综合健康分中的权重。为 None 时使用 DEFAULT_DIMENSION_WEIGHTS。
    geometric_weights : Optional[Mapping[str, float]], default None
        五维在几何加权综合得分中的权重。为 None 时使用 GEOMETRIC_DIMENSION_WEIGHTS。

    返回
    -------
    PortfolioDimensions
        包含五维得分、算术加权综合健康分及几何加权综合得分的不可变数据对象。
    """
    if dimension_weights is None:
        dimension_weights = DEFAULT_DIMENSION_WEIGHTS
    if geometric_weights is None:
        geometric_weights = GEOMETRIC_DIMENSION_WEIGHTS

    drawdown = compute_drawdown_control(dfs, weights)
    diversification = compute_portfolio_diversification(dfs, weights)
    efficiency = compute_position_efficiency(dfs, weights)
    stability = compute_return_stability(dfs, weights)
    style = compute_style_balance(dfs, weights)

    score_dict = {
        "drawdown_control": drawdown.score,
        "portfolio_diversification": diversification.score,
        "position_efficiency": efficiency.score,
        "return_stability": stability.score,
        "style_balance": style.score,
    }

    composite_score = sum(dimension_weights[dim] * score for dim, score in score_dict.items())
    geometric_composite_score = compute_geometric_composite_score(score_dict, geometric_weights)

    return PortfolioDimensions(
        drawdown_control=drawdown,
        portfolio_diversification=diversification,
        position_efficiency=efficiency,
        return_stability=stability,
        style_balance=style,
        composite_score=composite_score,
        geometric_composite_score=geometric_composite_score,
        dimension_weights=dict(dimension_weights),
    )


# ============================================================================
# Data loading helpers
# ============================================================================


def load_random_portfolio(n_assets: int = 5) -> List[pd.DataFrame]:
    """读取 recommender/portfolio_advisor/data 下的 df_1 ~ df_5 并返回 DataFrame 列表。

    注：历史函数名为 load_random_portfolio，现改为从 data_read.load_all()
    读取本地 parquet 数据，不再做随机抽取。n_assets 仅用于返回前 n 个 DataFrame。
    """
    data = load_all()
    if n_assets > len(data):
        raise ValueError(f"请求 {n_assets} 个资产，但 data_read 仅提供 {len(data)} 个")
    return [data[f"df_{i}"] for i in range(1, n_assets + 1)]


def _fmt(value: float) -> str:
    """格式化浮点数输出。"""
    if value is None:
        return "None"
    if isinstance(value, float) and (value == float("inf") or value == float("-inf")):
        return str(value)
    return f"{value:.4f}"


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    # 1. 读取 5 只随机标的
    dfs = load_random_portfolio(n_assets=5)
    weights = [0.1, 0.2, 0.3, 0.3, 0.1]

    codes = [str(df["code"].iloc[0]) for df in dfs]

    # 2. 计算五维诊断
    result = compute_portfolio_dimensions(dfs, weights)

    # 3. 打印结果
    print("=" * 70)
    print("组合标的:", codes)
    print("组合权重:", weights)
    print("=" * 70)

    print("【抗回撤能力】")
    print(f"  最大回撤 MDD       : {_fmt(result.drawdown_control.mdd)}")
    print(f"  控制得分 (0-100)   : {_fmt(result.drawdown_control.score)}")

    print("\n【资产分散度】")
    print(f"  ENB (weight-based) : {_fmt(result.portfolio_diversification.enb_weight_based)}")
    print(f"  ENB (risk-based)   : {_fmt(result.portfolio_diversification.enb_risk_based)}")
    print(f"  分散得分 (0-100)   : {_fmt(result.portfolio_diversification.score)}")

    print("\n【持仓性价比】")
    print(f"  夏普比率           : {_fmt(result.position_efficiency.sharpe_ratio)}")
    print(f"  性价比得分 (0-100) : {_fmt(result.position_efficiency.score)}")

    print("\n【收益稳定性】")
    print(f"  年化波动率         : {_fmt(result.return_stability.annualized_volatility)}")
    print(f"  稳定得分 (0-100)   : {_fmt(result.return_stability.score)}")

    print("\n【风格均衡】")
    print(f"  风格 HHI           : {_fmt(result.style_balance.style_hhi)}")
    print(f"  有效风格数         : {_fmt(result.style_balance.effective_style_num)}")
    print(f"  均衡得分 (0-100)   : {_fmt(result.style_balance.score)}")

    print("\n" + "=" * 70)
    print("综合健康分 (0-100)   :", _fmt(result.composite_score))
    print("几何加权综合分 (0-100):", _fmt(result.geometric_composite_score))
    print("维度权重             :", dict(result.dimension_weights))
    print("几何加权权重         :", dict(GEOMETRIC_DIMENSION_WEIGHTS))
    print("=" * 70)
