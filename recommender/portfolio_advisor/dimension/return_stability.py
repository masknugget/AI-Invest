"""
    年化波动率（Annualized Volatility）及 风险归一化打分
"""
import pandas as pd
import numpy as np
from typing import List, Union, Optional

def calculate_annualized_volatility(
    dfs: List[pd.DataFrame],
    weights: Union[List[float], np.ndarray],
    risk_free_rate: float = 0.03,
    annualization_factor: float = 252.0,
    return_col: str = "pctChg",
    date_col: str = "date",
) -> float:
    """
    计算投资组合的年化波动率。

    使用协方差矩阵法：σ_p = sqrt(w^T · Σ · w) * sqrt(annualization_factor)

    参数
    ----------
    dfs : List[pd.DataFrame]
        n 个 pandas DataFrame，每个代表一个资产的历史行情数据。
        所有 DataFrame 必须包含相同的列名，至少包含 `date_col` 和 `return_col`。
    weights : Union[List[float], np.ndarray]
        投资组合中各资产的权重，长度必须等于 len(dfs)，且所有权重之和为 1。
    risk_free_rate : float, default 0.03
        无风险利率（本函数中仅作参数保留，实际波动率计算不直接使用）。
    annualization_factor : float, default 252.0
        年化乘数。日频数据通常用 252，周频用 52，月频用 12。
    return_col : str, default "pctChg"
        用于计算收益率的列名。若数据中没有该列，可使用 "close" 自行计算收益率。
    date_col : str, default "date"
        日期列名，用于对齐多个资产的收益率序列。

    返回
    -------
    float
        投资组合的年化波动率。
    """
    # ---------- 输入校验 ----------
    n = len(dfs)
    if n == 0:
        raise ValueError("dfs 不能为空，至少需要 1 个资产数据。")

    weights = np.asarray(weights, dtype=float)
    if weights.shape[0] != n:
        raise ValueError(f"权重数量 ({weights.shape[0]}) 必须与资产数量 ({n}) 一致。")
    if not np.isclose(weights.sum(), 1.0):
        raise ValueError(f"权重之和必须等于 1，当前为 {weights.sum():.6f}。")

    # ---------- 提取收益率序列 ----------
    returns_list: List[pd.Series] = []
    for i, df in enumerate(dfs):
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"dfs[{i}] 必须是 pandas DataFrame。")

        df_copy = df.copy()

        # 确保日期列存在并可排序
        if date_col not in df_copy.columns:
            raise ValueError(f"第 {i} 个 DataFrame 缺少日期列 '{date_col}'。")
        df_copy[date_col] = pd.to_datetime(df_copy[date_col])
        df_copy = df_copy.sort_values(by=date_col).reset_index(drop=True)

        # 获取收益率
        if return_col in df_copy.columns:
            # 假设 pctChg 可能是百分比形式（如 1.5 表示 1.5%），自动转换为小数
            ret = pd.to_numeric(df_copy[return_col], errors="coerce")
            if ret.abs().max() > 1:
                ret = ret / 100.0
        elif "close" in df_copy.columns:
            # 使用收盘价计算对数收益率
            close = pd.to_numeric(df_copy["close"], errors="coerce")
            ret = np.log(close / close.shift(1)).dropna()
        else:
            raise ValueError(
                f"第 {i} 个 DataFrame 既无 '{return_col}' 列也无 'close' 列，无法计算收益率。"
            )

        # 以日期为索引
        ret_series = pd.Series(ret.values, index=df_copy[date_col].values, name=f"asset_{i}")
        # 去除重复日期，保留最后一条记录（避免数据源中存在重复交易日）
        ret_series = ret_series[~ret_series.index.duplicated(keep="last")]
        ret_series = ret_series.dropna()
        returns_list.append(ret_series)

    # ---------- 对齐日期 ----------
    # 使用 concat 进行 inner join，只保留所有资产都有的交易日
    aligned_returns = pd.concat(returns_list, axis=1, join="inner")

    if aligned_returns.empty:
        raise ValueError("对齐日期后无共同交易日数据，请检查输入数据的日期范围。")

    if len(aligned_returns) < 2:
        raise ValueError("对齐后的共同交易日不足 2 天，无法计算波动率。")

    # ---------- 计算年化波动率 ----------
    # 组合波动率 = sqrt(w^T * Σ * w) * sqrt(annualization_factor)
    # 其中 Σ 是日收益率的协方差矩阵
    cov_matrix = aligned_returns.cov().values

    # 投资组合方差
    portfolio_variance = weights.T @ cov_matrix @ weights

    if portfolio_variance < 0:
        # 数值误差可能导致极小的负数，取 0
        portfolio_variance = 0.0

    portfolio_volatility = np.sqrt(portfolio_variance) * np.sqrt(annualization_factor)

    return float(portfolio_volatility)


def normalize_volatility_to_score(volatility: float) -> float:
    """
    将计算得到的投资组合年化波动率（或最大回撤等风险指标）映射为 0-100 的归一化分数。

    基于金融逻辑的标尺映射法（分段线性插值）：
    - 0% (0.0) -> 得分 0 (无风险资产)
    - 10% (0.1) -> 得分 20 (低波动策略)
    - 20% (0.2) -> 得分 50 (基准中等风险)
    - 40% (0.4) -> 得分 80 (高风险策略)
    - 80% (0.8) -> 得分 100 (极端危机/极小概率高杠杆，设为软上限)

    对于超过 80% 或低于 0% 的输入，直接截断 (Clip) 为 100 和 0。

    参数
    ----------
    volatility : float
        计算得出的风险数值（如年化波动率），以小数形式表示（例如 0.2676 表示 26.76%）。

    返回
    -------
    float
        归一化后的风险分数，范围在 [0, 100] 之间。
    """
    # 定义锚点
    anchor_vols = np.array([0.0, 0.1, 0.2, 0.4, 0.8])
    anchor_scores = np.array([0.0, 20.0, 50.0, 80.0, 100.0])

    # 使用 numpy 的 interp 进行分段线性插值
    # 默认情况下，np.interp 会自动将小于 0.0 的值截断为 0.0，大于 0.8 的值截断为 100.0
    score = np.interp(volatility, anchor_vols, anchor_scores)

    # 为了确保绝对的边界安全，再进行一次显式的截断
    score = np.clip(score, 0.0, 100.0)

    return float(score)


if __name__ == "__main__":
    # 简单测试归一化函数
    test_vol = 0.2676
    print(f"输入波动率/回撤值: {test_vol}")
    print(f"归一化得分: {normalize_volatility_to_score(test_vol):.2f}")  # 预期输出: 60.14

    test_vol_2 = 0.05
    print(f"输入波动率/回撤值: {test_vol_2}")
    print(f"归一化得分: {normalize_volatility_to_score(test_vol_2):.2f}")  # 预期输出: 10.00

    test_vol_3 = 0.95
    print(f"输入波动率/回撤值: {test_vol_3}")
    print(f"归一化得分: {normalize_volatility_to_score(test_vol_3):.2f}")  # 预期输出: 100.00
