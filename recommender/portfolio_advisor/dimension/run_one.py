"""
单只股票五维诊断 - 运行入口

输入：1 只标的的日频行情 DataFrame + 权重 [1.0]
输出：5 个维度的原始指标 + 0-100 评分 + 综合健康分

实现直接复用 run.py 中的组合维度函数；对于单只股票，风格均衡维度退化处理。
"""

import random

import pandas as pd

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.run import (
    DEFAULT_DIMENSION_WEIGHTS,
    GEOMETRIC_DIMENSION_WEIGHTS,
    PortfolioDimensions,
    StyleBalance,
    compute_drawdown_control,
    compute_geometric_composite_score,
    compute_portfolio_diversification,
    compute_position_efficiency,
    compute_return_stability,
)


def compute_stock_dimensions(
    dfs: pd.DataFrame,
) -> PortfolioDimensions:
    """
    计算单只股票的五维诊断结果与综合健康分。

    参数
    ----------
    dfs : pd.DataFrame
        单只股票的日频行情 DataFrame，至少包含 'date'、'close'、'pctChg' 列。

    返回
    -------
    PortfolioDimensions
        与 run.py 一致的五维诊断结果对象。
    """
    if not isinstance(dfs, pd.DataFrame):
        raise TypeError("dfs 必须是单只股票的 pandas DataFrame")

    stock_dfs = [dfs]
    stock_weights = [1.0]

    drawdown = compute_drawdown_control(stock_dfs, stock_weights)
    diversification = compute_portfolio_diversification(stock_dfs, stock_weights)
    efficiency = compute_position_efficiency(stock_dfs, stock_weights)
    stability = compute_return_stability(stock_dfs, stock_weights)

    # 单只股票无法做组合层面的风格分散（HHI=1，有效风格数=1），
    # 但为保持几何加权综合分的区分度，赋予中性风格分 50.0，
    # 表示单股场景下风格信息未知，不惩罚也不奖励。
    style = StyleBalance(
        style_hhi=1.0,
        effective_style_num=1.0,
        score=50.0,
    )

    score_dict = {
        "drawdown_control": drawdown.score,
        "portfolio_diversification": diversification.score,
        "position_efficiency": efficiency.score,
        "return_stability": stability.score,
        "style_balance": style.score,
    }

    composite_score = sum(
        DEFAULT_DIMENSION_WEIGHTS[dim] * score for dim, score in score_dict.items()
    )
    geometric_composite_score = compute_geometric_composite_score(
        score_dict, GEOMETRIC_DIMENSION_WEIGHTS
    )

    return PortfolioDimensions(
        drawdown_control=drawdown,
        portfolio_diversification=diversification,
        position_efficiency=efficiency,
        return_stability=stability,
        style_balance=style,
        composite_score=composite_score,
        geometric_composite_score=geometric_composite_score,
        dimension_weights=dict(DEFAULT_DIMENSION_WEIGHTS),
    )


# ============================================================================
# Data loading helpers
# ============================================================================


def load_random_stock() -> pd.DataFrame:
    """从 data_read.load_all() 返回的 df_1 ~ df_5 中随机抽取 1 只标的的行情数据。"""
    return random.choice(list(load_all().values()))


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
    df = load_random_stock()
    code = str(df["code"].iloc[0])

    result = compute_stock_dimensions(df)

    print("=" * 70)
    print("标的代码:", code)
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
