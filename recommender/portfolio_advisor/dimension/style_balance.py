"""
风格均衡（Style Balance）指标计算模块

style_balance:
    风格赫芬达尔指数（HHI）
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Union
import warnings


# ============================================================================
# 内部辅助函数
# ============================================================================

def _extract_latest_cross_section(
    dataframes: List[pd.DataFrame],
    date: Optional[str] = None,
    date_col: str = 'date'
) -> Tuple[pd.DataFrame, List[int]]:
    """
    从 n 个资产的时间序列数据中提取统一日期的横截面数据。

    当 ``date`` 为 None 时，使用所有资产最新日期的最小值，
    确保横截面一致性（所有资产在同一交易日有数据）。

    参数:
        dataframes: n 个资产的 DataFrame 列表
        date: 指定日期字符串，如 ``'2024-01-15'``；None 则自动确定
        date_col: 日期列名

    返回:
        (横截面 DataFrame, 有效资产原始索引列表)
    """
    if not dataframes:
        raise ValueError("dataframes 不能为空列表")

    # 确定目标日期
    if date is not None:
        target = pd.to_datetime(date).normalize()
    else:
        latest_dates = []
        for df in dataframes:
            if not df.empty and date_col in df.columns:
                latest = pd.to_datetime(df[date_col]).max().normalize()
                latest_dates.append(latest)

        if not latest_dates:
            raise ValueError("无法从 dataframes 中确定最新日期")

        # 取所有资产最新日期的最小值，保证横截面一致性
        target = min(latest_dates)

    records = []
    valid_indices = []

    for i, df in enumerate(dataframes):
        if df.empty:
            warnings.warn(f"第 {i} 个 DataFrame 为空，已跳过")
            continue

        df_copy = df.copy()
        if date_col not in df_copy.columns:
            warnings.warn(f"第 {i} 个 DataFrame 缺少 '{date_col}' 列，已跳过")
            continue

        df_copy[date_col] = pd.to_datetime(df_copy[date_col]).dt.normalize()

        # 取小于等于目标日期的最新数据
        valid = df_copy[df_copy[date_col] <= target]
        if valid.empty:
            warnings.warn(f"第 {i} 个资产在 {target.date()} 及之前无数据，已跳过")
            continue

        latest_date = valid[date_col].max()
        row = valid[valid[date_col] == latest_date].iloc[[-1]].copy()
        records.append(row)
        valid_indices.append(i)

    if not records:
        raise ValueError(f"在 {target.date()} 及之前没有有效的横截面数据")

    cs_df = pd.concat(records, ignore_index=True)
    return cs_df, valid_indices


def _winsorize_series(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """
    对 Series 进行缩尾处理，抑制极端异常值。

    参数:
        s: 输入序列
        lower: 下分位数，默认 1%
        upper: 上分位数，默认 99%

    返回:
        缩尾后的序列
    """
    q_low = s.quantile(lower)
    q_high = s.quantile(upper)
    return s.clip(q_low, q_high)


def _compute_size_score(df: pd.DataFrame) -> pd.Series:
    """
    计算规模得分，用于区分大盘 / 中盘 / 小盘。

    使用成交额（close × volume）作为流通市值的代理变量，
    经对数变换和缩尾处理后标准化到 [0, 1]。

    参数:
        df: 横截面 DataFrame

    返回:
        规模得分序列
    """
    required = ['close', 'volume']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"计算规模得分缺少列: {missing}")

    size_proxy = df['close'].astype(float) * df['volume'].astype(float)
    size_proxy = np.log1p(size_proxy)
    size_proxy = _winsorize_series(size_proxy)

    min_val = size_proxy.min()
    max_val = size_proxy.max()
    if max_val - min_val < 1e-10:
        return pd.Series(0.5, index=df.index)

    return (size_proxy - min_val) / (max_val - min_val)


def _compute_value_score(df: pd.DataFrame) -> pd.Series:
    """
    计算估值得分，用于区分价值 / 均衡 / 成长。

    基于 PE、PB、PS、PCF 的倒数综合计算。最终标准化到 [0, 1]。

    参数:
        df: 横截面 DataFrame

    返回:
        估值得分序列
    """
    value_cols = ['peTTM', 'pbMRQ', 'psTTM', 'pcfNcfTTM']
    available = [c for c in value_cols if c in df.columns]

    indicators = []
    for col in available:
        s = df[col].astype(float).copy()
        s = s.where(s > 0, np.nan)
        if s.isna().all():
            continue
        s = s.fillna(s.median())
        s = _winsorize_series(s)
        indicators.append(1.0 / s)

    if not indicators:
        warnings.warn("无有效估值指标，使用价格倒数作为估值代理")
        price = _winsorize_series(df['close'].astype(float))
        min_p, max_p = price.min(), price.max()
        if max_p - min_p < 1e-10:
            return pd.Series(0.5, index=df.index)
        return 1.0 - (price - min_p) / (max_p - min_p)

    value_score = pd.concat(indicators, axis=1).mean(axis=1)
    value_score = _winsorize_series(value_score)

    min_val = value_score.min()
    max_val = value_score.max()
    if max_val - min_val < 1e-10:
        return pd.Series(0.5, index=df.index)

    return (value_score - min_val) / (max_val - min_val)


def _assign_style_buckets(
    size_scores: pd.Series,
    value_scores: pd.Series,
    n_buckets: int = 3
) -> pd.Series:
    """
    基于规模得分和估值得分，将资产分配到风格桶。
    """
    size_labels = ['small', 'mid', 'large'] if n_buckets == 3 else [f'S{i+1}' for i in range(n_buckets)]
    size_buckets = pd.qcut(
        size_scores,
        q=n_buckets,
        labels=size_labels,
        duplicates='drop'
    )

    value_labels = ['growth', 'blend', 'value'] if n_buckets == 3 else [f'V{i+1}' for i in range(n_buckets)]
    value_buckets = pd.qcut(
        value_scores,
        q=n_buckets,
        labels=value_labels,
        duplicates='drop'
    )

    return size_buckets.astype(str) + '_' + value_buckets.astype(str)


# ============================================================================
# 主计算函数
# ============================================================================

def calculate_style_hhi(
    dataframes: List[pd.DataFrame],
    weights: List[float],
    risk_free_rate: float = 0.03,
    date: Optional[str] = None,
    n_buckets: int = 3
) -> Dict[str, Union[float, Dict, List, int, str]]:
    """
    计算风格赫芬达尔指数

    参数:
        dataframes: n 个资产的 DataFrame 列表
        weights: n 个资产的权重列表
        risk_free_rate: 无风险利率
        date: 计算 HHI 的日期
        n_buckets: 每个风格维度的分组数

    返回:
        包含 HHI 及相关指标的字典
    """
    if not dataframes:
        raise ValueError("dataframes 不能为空列表")

    n_input = len(dataframes)
    if len(weights) != n_input:
        raise ValueError(f"资产数量({n_input})与权重数量({len(weights)})不匹配")

    total_weight = sum(weights)
    if abs(total_weight - 1.0) > 1e-6:
        raise ValueError(f"权重之和应为 1.0，当前为 {total_weight:.6f}")

    if any(w < 0 for w in weights):
        raise ValueError("权重不能包含负数")

    if n_buckets < 2:
        raise ValueError("n_buckets 至少为 2")

    cs_df, valid_indices = _extract_latest_cross_section(dataframes, date=date)

    n_valid = len(cs_df)
    if n_valid == 0:
        raise ValueError("没有有效的资产数据可用于计算")

    valid_weights = [weights[i] for i in valid_indices]
    weight_sum = sum(valid_weights)
    valid_weights = [w / weight_sum for w in valid_weights]

    cs_df = cs_df.reset_index(drop=True)
    cs_df['weight'] = valid_weights

    size_score = _compute_size_score(cs_df)
    value_score = _compute_value_score(cs_df)

    cs_df['size_score'] = size_score
    cs_df['value_score'] = value_score

    cs_df['style_bucket'] = _assign_style_buckets(size_score, value_score, n_buckets)

    style_weights = cs_df.groupby('style_bucket')['weight'].sum()

    style_hhi = float((style_weights ** 2).sum())

    total_styles = n_buckets * n_buckets
    actual_styles = len(style_weights)

    effective_style_num = float(1.0 / style_hhi) if style_hhi > 1e-12 else float('inf')

    if actual_styles <= 1:
        style_diversification = 0.0
    else:
        min_hhi = 1.0 / actual_styles
        style_diversification = float((1.0 - style_hhi) / (1.0 - min_hhi))

    max_style_weight = float(style_weights.max())

    keep_cols = ['code', 'size_score', 'value_score', 'style_bucket', 'weight']
    available_cols = [c for c in keep_cols if c in cs_df.columns]
    style_classification = cs_df[available_cols].to_dict('records')

    if 'date' in cs_df.columns:
        calc_date = pd.to_datetime(cs_df['date'].iloc[0]).strftime('%Y-%m-%d')
    else:
        calc_date = str(date) if date else 'latest'

    return {
        'style_hhi': style_hhi,
        'effective_style_num': effective_style_num,
        'style_diversification': style_diversification,
        'max_style_weight': max_style_weight,
        'style_weights': {str(k): float(v) for k, v in style_weights.items()},
        'style_classification': style_classification,
        'n_buckets': n_buckets,
        'total_styles': total_styles,
        'actual_styles': actual_styles,
        'risk_free_rate': float(risk_free_rate),
        'calculation_date': calc_date,
        'n_assets': n_valid
    }


# ============================================================================
# 归一化评分函数 (补充代码)
# ============================================================================

def normalize_style_hhi_to_score(style_hhi: float, n_styles: int) -> float:
    """
    将计算得到的风格 HHI 归一化映射到 [0, 100] 的均衡度评分。

    采用“理论上下限绝对映射”策略：
    - HHI 上限 (1.0)：完全集中单一风格，映射得分为 0
    - HHI 下限 (1/N)：完全等权分布于 N 种风格，映射得分为 100

    包含防御性截断逻辑，处理实盘中多空对冲或计算误差导致的越界问题。

    参数:
        style_hhi (float): 原始计算的风格赫芬达尔指数
        n_styles (int): 风格池分类的总数量 (如 n_buckets * n_buckets)

    返回:
        float: 归一化后的均衡度得分，范围严格在 [0, 100]
    """
    if n_styles <= 1:
        raise ValueError("风格分类数 n_styles 必须大于 1")

    hhi_max = 1.0
    hhi_min = 1.0 / n_styles

    # 防御性截断：保证 HHI 落在合理的理论极值区间内
    hhi_clipped = np.clip(style_hhi, hhi_min, hhi_max)

    # 线性映射公式: Score = 100 * (HHI_max - HHI) / (HHI_max - HHI_min)
    score = 100.0 * (hhi_max - hhi_clipped) / (hhi_max - hhi_min)

    return float(score)
