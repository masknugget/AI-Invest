"""
组合性价比计算模块

    夏普比率（Sharpe Ratio） 是最合适、最通用的"组合性价比"指标
"""
import pandas as pd
import numpy as np
from typing import List


def _extract_daily_returns(df: pd.DataFrame) -> pd.Series:
    """
    从单个资产 DataFrame 中提取日收益率序列，以 date 为索引。

    Parameters
    ----------
    df : pd.DataFrame
        单只资产的数据，必须包含 'date' 列，以及 'pctChg' 或 'close'/'preclose' 列。

    Returns
    -------
    pd.Series
        以日期为索引的日收益率序列（小数形式，如 0.01 表示 1%）。
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    # 去除重复日期：同一天若出现多条记录，保留最后一条
    df = df.drop_duplicates(subset="date", keep="last")
    df = df.sort_values("date").set_index("date")

    if "pctChg" in df.columns:
        # pctChg 通常为百分比数值，需转为小数
        return (df["pctChg"] / 100).rename("daily_return")
    else:
        # 通过收盘价与前收盘价计算
        return (df["close"] / df["preclose"] - 1).rename("daily_return")


def _align_returns(returns_list: List[pd.Series]) -> pd.DataFrame:
    """
    按日期对齐多个资产的日收益率序列，丢弃日期不匹配的行。

    Parameters
    ----------
    returns_list : List[pd.Series]
        各资产的日收益率序列。

    Returns
    -------
    pd.DataFrame
        对齐后的收益率矩阵，形状为 (T, n)，T 为交易日数，n 为资产数。

    Raises
    ------
    ValueError
        如果对齐后没有任何有效数据。
    """
    aligned = pd.concat(returns_list, axis=1).dropna()
    if aligned.empty:
        raise ValueError("对齐后无有效数据，请检查各资产的日期范围是否一致")
    return aligned


def _compute_portfolio_returns(returns_df: pd.DataFrame, weights: np.ndarray) -> np.ndarray:
    """
    计算投资组合的日收益率向量。

    Parameters
    ----------
    returns_df : pd.DataFrame
        对齐后的资产收益率矩阵，形状 (T, n)。
    weights : np.ndarray
        资产权重向量，形状 (n,)，之和为 1。

    Returns
    -------
    np.ndarray
        组合日收益率向量，形状 (T,)。
    """
    return returns_df.values @ weights


def _annualize_metrics(
    mean_daily_return: float,
    std_daily_return: float,
    trading_days: int = 252,
) -> tuple[float, float]:
    """
    将日均收益率和日波动率进行年化处理。

    Parameters
    ----------
    mean_daily_return : float
        日均收益率。
    std_daily_return : float
        日收益率标准差（样本标准差）。
    trading_days : int, default 252
        一年的交易日数量。

    Returns
    -------
    tuple[float, float]
        (年化收益率, 年化波动率)
    """
    annual_return = mean_daily_return * trading_days
    annual_volatility = std_daily_return * np.sqrt(trading_days)
    return annual_return, annual_volatility


def normalize_sharpe_to_score(sharpe_ratio: float) -> float:
    """
    将夏普比率归一化到 0~100 分（分段加权打分法）。

    映射规则：
        - sharpe < 0          → 0 分
        - 0 ≤ sharpe < 1      → 0 ~ 60 分（每单位 60 分）
        - 1 ≤ sharpe < 2      → 60 ~ 90 分（每单位 30 分）
        - 2 ≤ sharpe < 3      → 90 ~ 100 分（每单位 10 分）
        - sharpe ≥ 3          → 100 分

    Parameters
    ----------
    sharpe_ratio : float
        原始夏普比率。

    Returns
    -------
    float
        归一化后的分数（0~100）。
    """
    if sharpe_ratio < 0:
        return 0.0
    elif sharpe_ratio < 1:
        return sharpe_ratio * 60.0
    elif sharpe_ratio < 2:
        return 60.0 + (sharpe_ratio - 1.0) * 30.0
    elif sharpe_ratio < 3:
        return 90.0 + (sharpe_ratio - 2.0) * 10.0
    else:
        return 100.0


def calculate_portfolio_sharpe_ratio(
    dfs: List[pd.DataFrame],
    weights: List[float],
    risk_free_rate: float = 0.03,
    annual_trading_days: int = 252,
) -> float:
    """
    计算投资组合的夏普比率（Sharpe Ratio）。

    夏普比率衡量投资组合每承担一单位总风险，所能获得的超过无风险利率的额外收益，
    是评估组合"性价比"最通用、最核心的指标。

    计算公式：
        Sharpe Ratio = (E[R_p] - R_f) / σ_p

    其中：
        E[R_p] : 组合年化预期收益率
        R_f    : 年化无风险利率
        σ_p    : 组合年化收益率标准差（波动率）

    Parameters
    ----------
    dfs : List[pd.DataFrame]
        n 个资产的 pandas DataFrame 列表（n >= 1，通常 n < 20）。
        每个 DataFrame 的列名相同，必须包含 'date' 列，
        以及 'pctChg' 或 'close'/'preclose' 列。
    weights : List[float]
        各资产的持仓权重，长度与 dfs 相同，所有权重之和必须等于 1。
        例如：[0.5, 0.3, 0.2]。
    risk_free_rate : float, default 0.03
        年化无风险利率（默认 3%）。
    annual_trading_days : int, default 252
        一年的交易日数量，用于年化处理。

    Returns
    -------
    float
        投资组合的年化夏普比率。

    Raises
    ------
    ValueError
        当资产数量与权重数量不匹配，或权重之和不等于 1 时。
    """
    # ---------- 参数校验 ----------
    if len(dfs) != len(weights):
        raise ValueError(
            f"资产数量 ({len(dfs)}) 与权重数量 ({len(weights)}) 不匹配"
        )

    if not np.isclose(sum(weights), 1.0):
        raise ValueError(f"权重之和必须等于 1，当前为 {sum(weights)}")

    # ---------- 提取并对齐日收益率 ----------
    returns_list = [_extract_daily_returns(df) for df in dfs]
    aligned_returns = _align_returns(returns_list)

    # ---------- 计算组合日收益率 ----------
    weights_arr = np.array(weights)
    portfolio_returns = _compute_portfolio_returns(aligned_returns, weights_arr)

    # ---------- 统计量计算 ----------
    mean_daily = np.mean(portfolio_returns)
    std_daily = np.std(portfolio_returns, ddof=1)  # 样本标准差

    # ---------- 年化 ----------
    annual_return, annual_volatility = _annualize_metrics(
        mean_daily, std_daily, annual_trading_days
    )

    # ---------- 夏普比率 ----------
    if annual_volatility == 0:
        # 避免除零：若收益高于无风险利率则正无穷，否则负无穷
        return float("inf") if annual_return > risk_free_rate else float("-inf")

    sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility
    return sharpe_ratio


def calculate_portfolio_sharpe_score(
    dfs: List[pd.DataFrame],
    weights: List[float],
    risk_free_rate: float = 0.03,
    annual_trading_days: int = 252,
) -> float:
    """
    计算投资组合的夏普比率得分（0~100 分）。

    先调用 calculate_portfolio_sharpe_ratio 计算原始夏普比率，
    再通过分段加权打分法归一化到 0~100 分。

    Parameters
    ----------
    dfs : List[pd.DataFrame]
        n 个资产的 pandas DataFrame 列表。
    weights : List[float]
        各资产的持仓权重，之和为 1。
    risk_free_rate : float, default 0.03
        年化无风险利率（默认 3%）。
    annual_trading_days : int, default 252
        一年的交易日数量。

    Returns
    -------
    float
        投资组合的夏普比率得分（0~100）。
    """
    sharpe = calculate_portfolio_sharpe_ratio(
        dfs, weights, risk_free_rate, annual_trading_days
    )
    return normalize_sharpe_to_score(sharpe)
