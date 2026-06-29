"""

Herfindahl 指数 HHI	Σwᵢ²	越小越分散	权重集中	范围 [1/N, 1]
有效资产数 Neff	1 / HHI	越大越分散	权重集中	范围 [1, N]，直观
CR_n 前n大权重和	Σᵢ₌₁ⁿ wᵢ	越小越分散	权重集中	常用 CR5、CR10
Gini 系数	基于权重 Lorentz 曲线	越小越分散	权重集中	对极端值不敏感
熵指数 Shannon Entropy	−Σwᵢ·ln(wᵢ)	越大越分散	权重集中	需归一化比较
分散比率 DR	Σ(wᵢσᵢ) / σp	越大越分散	风险贡献	>2 优秀，=1 无分散
有效下注数 ENB	(Σλ)² / Σλ²（PCA特征值）	越大越分散	风险贡献	范围 [1, N]，最严谨
风险贡献集中度	Σ(RCᵢ/σp)²	越小越分散	风险贡献	RCᵢ = wᵢ·(Σw)ᵢ/σp
平均相关系数	Σρᵢⱼ / C(n,2)	越小越分散	相关性	危机时会飙升
R² 系统风险占比	回归决定系数	越高越接近完全分散	相关性	过高则趋同指数
Active Share	½·Σ|wᵢ − wᵢᵇ|	越大越偏离基准	因子暴露
"""


"""
投资组合分散度与风险集中度指标计算模块
    有效下注数 (Effective Number of Bets, ENB)
"""
import pandas as pd
import numpy as np
from typing import List, Union


def effective_number_of_bets_weight_based(
    weights: Union[List[float], np.ndarray]
) -> float:
    """
    基于权重的有效下注数 (Weight-based ENB)。

    计算公式: ENB = 1 / Σ(w_i²)

    当权重完全平均分配时，ENB = n（资产数量）；
    当权重完全集中于单一资产时，ENB = 1。

    Args:
        weights: 各资产权重数组，元素之和应为1。

    Returns:
        有效下注数，取值范围 [1, n]。
    """
    weights_arr = np.asarray(weights, dtype=np.float64)

    if not np.isclose(weights_arr.sum(), 1.0, atol=1e-6):
        raise ValueError(f"权重之和必须等于1，当前为 {weights_arr.sum():.6f}")

    if np.any(weights_arr < 0):
        raise ValueError("权重不能为负数")

    sum_sq = np.sum(weights_arr ** 2)
    if sum_sq < 1e-12:
        return 1.0

    return float(1.0 / sum_sq)


def effective_number_of_bets_risk_based(
    weights: Union[List[float], np.ndarray],
    cov_matrix: Union[pd.DataFrame, np.ndarray],
) -> float:
    """
    基于风险贡献的有效下注数 (Risk-based ENB)。

    计算公式: ENB = (σ_p²)² / Σ(RC_i²)
    其中 σ_p² = w^T Σ w 是组合方差，
    RC_i = w_i · (Σw)_i 是第i个资产的绝对风险贡献。

    该指标考虑了资产之间的相关性，更能反映实际的风险分散程度。

    Args:
        weights: 各资产权重数组，长度应与cov_matrix维度一致，元素之和应为1。
        cov_matrix: 资产收益率的协方差矩阵，形状为 (n, n)。

    Returns:
        基于风险贡献的有效下注数，取值范围 [1, n]。
    """
    weights_arr = np.asarray(weights, dtype=np.float64)
    cov_arr = np.asarray(cov_matrix, dtype=np.float64)

    n = len(weights_arr)
    if cov_arr.shape != (n, n):
        raise ValueError(f"协方差矩阵形状 {cov_arr.shape} 与权重长度 {n} 不匹配")

    if not np.isclose(weights_arr.sum(), 1.0, atol=1e-6):
        raise ValueError(f"权重之和必须等于1，当前为 {weights_arr.sum():.6f}")

    # 组合方差
    portfolio_var = weights_arr @ cov_arr @ weights_arr

    if portfolio_var < 1e-12:
        # 如果组合方差接近0，说明所有资产无波动或完全对冲
        return float(n)

    # 边际风险贡献 = Σw
    marginal_risk = cov_arr @ weights_arr

    # 绝对风险贡献 = w_i · (Σw)_i
    risk_contributions = weights_arr * marginal_risk

    # 基于风险贡献的ENB
    sum_sq_rc = np.sum(risk_contributions ** 2)
    enb = (portfolio_var ** 2) / sum_sq_rc

    return float(enb)


def compute_enb_from_dataframes(
    dfs: List[pd.DataFrame],
    weights: Union[List[float], np.ndarray],
    risk_free_rate: float = 0.03,
    enb_type: str = "both",
) -> dict:
    """
    从多个 pandas DataFrame 计算投资组合的有效下注数 (ENB)。

    Args:
        dfs: 包含n个资产数据的DataFrame列表，每个DataFrame的列名必须一致，
             且包含 'date' 和 'pctChg' 列。
        weights: 各资产在投资组合中的权重，长度必须等于len(dfs)，元素之和应为1。
        risk_free_rate: 无风险利率，默认0.03。当前ENB计算中不直接使用，
                        但保留参数以符合接口规范。
        enb_type: 计算类型，可选 "weight"（基于权重）、"risk"（基于风险）、"both"（两者都计算）。

    Returns:
        包含ENB计算结果的字典。
    """
    n = len(dfs)
    weights_arr = np.asarray(weights, dtype=np.float64)

    if n == 0:
        raise ValueError("至少需要一个DataFrame")

    if len(weights_arr) != n:
        raise ValueError(f"权重数量 {len(weights_arr)} 与DataFrame数量 {n} 不匹配")

    if not np.isclose(weights_arr.sum(), 1.0, atol=1e-6):
        raise ValueError(f"权重之和必须等于1，当前为 {weights_arr.sum():.6f}")

    # 检查列名
    required_cols = {"date", "pctChg"}
    for i, df in enumerate(dfs):
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"第{i}个DataFrame缺少列: {missing}")

    # 合并收益率数据，按日期对齐
    merged = dfs[0][["date", "pctChg"]].copy()
    merged.columns = ["date", "pctChg_0"]

    for i in range(1, n):
        temp = dfs[i][["date", "pctChg"]].copy()
        temp.columns = ["date", f"pctChg_{i}"]
        merged = merged.merge(temp, on="date", how="inner")

    # 提取收益率矩阵 (T × n)
    returns = merged[[f"pctChg_{i}" for i in range(n)]].values

    # 计算协方差矩阵（单资产时退化为 1×1）
    cov_matrix = np.cov(returns, rowvar=False)
    cov_matrix = np.atleast_2d(cov_matrix)

    result = {}

    if enb_type in ("weight", "both"):
        result["enb_weight_based"] = effective_number_of_bets_weight_based(weights_arr)

    if enb_type in ("risk", "both"):
        result["enb_risk_based"] = effective_number_of_bets_risk_based(weights_arr, cov_matrix)

    # 补充信息
    result["num_assets"] = n
    result["weights"] = weights_arr.tolist()
    result["max_weight"] = float(weights_arr.max())
    result["min_weight"] = float(weights_arr.min())
    result["herfindahl_index"] = float(np.sum(weights_arr ** 2))

    return result


# ============================================
# 新增：ENB 归一化到 0-100 分数
# ============================================

def normalize_enb_to_score(
    enb: float,
    num_assets: int,
) -> float:
    """
    将基于权重的有效下注数 (ENB) 归一化到 0-100 的分数。

    逻辑：当组合有 N 个资产且等权配置时，ENB 的理论最大值为 N。
    归一化后的分数表示当前组合达到了理论最大分散度的百分比。

    公式: Score = (ENB / N) × 100

    例如:
        - N = 10, ENB = 4.4444 → Score = 44.44
        - N = 10, ENB = 10.0   → Score = 100.0 (完全等权，最大分散)
        - N = 10, ENB = 1.0    → Score = 10.0  (完全集中，最小分散)

    Args:
        enb: 基于权重的有效下注数 (Weight-based ENB)，取值范围 [1, N]。
        num_assets: 组合中的资产总数 N。

    Returns:
        归一化后的分散度分数，取值范围 [100/N, 100]。
        当 N=1 时，始终返回 100.0。

    Raises:
        ValueError: 当 num_assets < 1 或 enb 不在有效范围 [1, num_assets] 内时。
    """
    if num_assets < 1:
        raise ValueError(f"资产数量必须 >= 1，当前为 {num_assets}")

    if enb < 1.0 or enb > num_assets:
        raise ValueError(
            f"ENB 值 {enb} 超出有效范围 [1, {num_assets}]，"
            f"请检查输入是否为基于权重的 ENB 以及资产数量是否正确"
        )

    # 单资产组合，始终为满分
    if num_assets == 1:
        return 100.0

    score = (enb / num_assets) * 100.0
    return float(score)


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    # 示例：10 个资产，权重 ENB = 4.4444
    enb_value = 4.4444
    n_assets = 10

    score = normalize_enb_to_score(enb_value, n_assets)
    print(f"ENB = {enb_value}, N = {n_assets} → Score = {score:.2f}")
    # 输出: ENB = 4.4444, N = 10 → Score = 44.44

    # 示例：完全等权配置
    weights_equal = [0.1] * 10
    enb_max = effective_number_of_bets_weight_based(weights_equal)
    score_max = normalize_enb_to_score(enb_max, 10)
    print(f"等权 ENB = {enb_max:.2f} → Score = {score_max:.2f}")
    # 输出: 等权 ENB = 10.00 → Score = 100.00