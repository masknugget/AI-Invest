"""
历史极端行情压力测试 —— 历史回撤模拟（对应 FR-001）

设计原则：
- 纯函数，无模块级 I/O（不直接实例化 FileVisitor / IndustryQuery）
- 仅负责历史场景下的回撤计算与组合损失模拟
- 返回普通 dict，便于上层 stress_test.py 包装为 dataclass

核心公式：
    组合损失 = Σ(各基金持仓权重 × 该基金在历史场景下的最大回撤)

核心能力：
1. 单票在指定历史区间内的最大回撤（drawdown）
2. 组合在历史场景下的加权损失
3. 批量多场景计算
4. 组合净值/回撤时间序列模拟

使用示例：
    from research.portfolio_advisor.stress_portfolio.history_stress import (
        calculate_historical_drawdown,
        compute_historical_stress,
        list_historical_scenario_names,
    )

    portfolio = [
        {"code": "TEST_A", "weight": 1.0, "amount": 100000},
    ]
    dfs_map = {"TEST_A": df_a}
    results = compute_historical_stress(portfolio, dfs_map)
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from recommender.portfolio_advisor.stress_portfolio.const import (
    HISTORICAL_SCENARIOS,
    StressScenario,
    build_scenarios,
)


__all__ = [
    "calculate_historical_drawdown",
    "calculate_historical_scenario_result",
    "compute_historical_stress",
    "simulate_portfolio_drawdown",
    "list_historical_scenario_names",
]


# ============================================================================
# 私有辅助函数
# ============================================================================
def _ensure_portfolio_df(portfolio: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    将持仓列表转换为 DataFrame，校验并补全 amount 列。

    参数
    ----------
    portfolio : List[Dict]
        持仓列表，每个元素至少包含 code、weight；可选 amount。

    返回
    -------
    pd.DataFrame
        包含 code、weight、amount 列的持仓 DataFrame。

    异常
    ----
    ValueError
        持仓为空、缺少必要列或权重之和不为 1 时抛出。
    """
    if not portfolio:
        raise ValueError("portfolio cannot be empty")

    portfolio_df = pd.DataFrame(portfolio)
    required = {"code", "weight"}
    missing = required - set(portfolio_df.columns)
    if missing:
        raise ValueError(f"portfolio missing required columns: {missing}")

    portfolio_df = portfolio_df.copy()
    if "amount" not in portfolio_df.columns:
        portfolio_df["amount"] = portfolio_df["weight"]

    total_weight = portfolio_df["weight"].sum()
    if not abs(total_weight - 1.0) < 1e-5:
        raise ValueError(f"权重之和必须等于 1，当前为 {total_weight}")

    return portfolio_df


def _load_single_df(code: str, dfs_map: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    """从 dfs_map 获取单票数据，支持多种 code 格式。"""
    if code in dfs_map:
        return dfs_map[code]

    # 兼容大小写与交易所前缀差异（sh. / sz. / 无后缀）
    norm = code.lower().replace("sh.", "").replace("sz.", "").replace(".", "")
    for k, v in dfs_map.items():
        k_norm = k.lower().replace("sh.", "").replace("sz.", "").replace(".", "")
        if k_norm == norm:
            return v
    return None


def _filter_by_date_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """
    按日期范围过滤 DataFrame，兼容字符串与 datetime 类型的 date 列。

    返回过滤后 DataFrame 的副本，保留原始 date 列的格式。
    """
    try:
        df_dates = pd.to_datetime(df["date"])
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
    except (ValueError, TypeError):
        df_dates = df["date"]
        start = start_date
        end = end_date

    mask = (df_dates >= start) & (df_dates <= end)
    return df.loc[mask].copy()


# ============================================================================
# 核心计算函数
# ============================================================================
def calculate_historical_drawdown(
    df: pd.DataFrame,
    scenario_params: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """
    基于已有时间序列数据，计算单票在极端行情下的最大回撤。

    参数
    ----------
    df : pd.DataFrame
        日度数据，必须包含 date、close、code 列。
    scenario_params : dict
        场景定义，包含 start_date、end_date。

    返回
    -------
    dict or None
        若场景区间内无数据返回 None；
        否则返回含 code、max_drawdown、peak_date、trough_date 的字典。
    """
    if df.empty or "close" not in df.columns or "date" not in df.columns:
        return None

    scenario_df = _filter_by_date_range(
        df,
        scenario_params["start_date"],
        scenario_params["end_date"],
    ).sort_values("date").reset_index(drop=True)

    if scenario_df.empty:
        return None

    close = pd.to_numeric(scenario_df["close"], errors="coerce")
    valid_mask = close.notna()
    if not valid_mask.any():
        return None

    scenario_df = scenario_df.loc[valid_mask].reset_index(drop=True)
    close = close.loc[valid_mask].reset_index(drop=True)

    peak = close.cummax()
    drawdown = (close - peak) / peak
    max_drawdown = drawdown.min()

    peak_idx = close.idxmax()
    trough_idx = drawdown.idxmin()

    return {
        "code": str(scenario_df["code"].iloc[0]),
        "max_drawdown": round(float(max_drawdown), 4),
        "peak_date": scenario_df.loc[peak_idx, "date"],
        "trough_date": scenario_df.loc[trough_idx, "date"],
    }


def calculate_historical_scenario_result(
    portfolio_df: pd.DataFrame,
    scenario: StressScenario,
    dfs_map: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    计算单个历史极端事件场景下的组合损失。

    参数
    ----------
    portfolio_df : pd.DataFrame
        包含 code、weight、amount 的持仓数据。
    scenario : StressScenario
        历史场景定义。
    dfs_map : Dict[str, pd.DataFrame]
        股票代码 -> 行情 DataFrame 的映射。

    返回
    -------
    dict
        {
            "scenario_id": 场景 ID,
            "scenario_name": 场景名称,
            "scenario_type": "historical",
            "start_date": 场景起始日期,
            "end_date": 场景结束日期,
            "benchmark_drawdown": 基准指数回撤,
            "portfolio_value": 组合总市值,
            "portfolio_loss_pct": 组合损失百分比（保留 1 位小数，负数）,
            "portfolio_loss_amount": 组合损失金额,
            "per_asset": 逐票明细列表,
            "warnings": 警告信息,
        }
    """
    portfolio_df = portfolio_df.copy()
    if "amount" not in portfolio_df.columns:
        portfolio_df["amount"] = portfolio_df["weight"]

    warnings: List[str] = []
    per_asset: List[Dict[str, Any]] = []
    weighted_drawdown = 0.0

    for _, row in portfolio_df.iterrows():
        code = row["code"]
        weight = float(row["weight"])
        amount = float(row["amount"])

        df = _load_single_df(code, dfs_map)
        if df is None or df.empty:
            warnings.append(f"缺少股票 {code} 的历史行情数据，该股票在该场景下回撤记为 0")
            per_asset.append(
                {
                    "code": code,
                    "weight": weight,
                    "amount": amount,
                    "drawdown": 0.0,
                    "loss_amount": 0.0,
                    "peak_date": None,
                    "trough_date": None,
                }
            )
            continue

        hist = calculate_historical_drawdown(df, scenario.params)
        if hist is None:
            warnings.append(
                f"股票 {code} 在场景 {scenario.name} 的时间区间内无数据，回撤记为 0"
            )
            drawdown = 0.0
        else:
            drawdown = hist["max_drawdown"]

        loss_amount = amount * drawdown
        weighted_drawdown += weight * drawdown

        per_asset.append(
            {
                "code": code,
                "weight": weight,
                "amount": amount,
                "drawdown": drawdown,
                "loss_amount": loss_amount,
                "peak_date": hist.get("peak_date") if hist else None,
                "trough_date": hist.get("trough_date") if hist else None,
            }
        )

    portfolio_value = float(portfolio_df["amount"].sum())
    portfolio_loss_amount = portfolio_value * weighted_drawdown

    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "scenario_type": scenario.type,
        "start_date": scenario.params.get("start_date"),
        "end_date": scenario.params.get("end_date"),
        "benchmark_drawdown": scenario.params.get("benchmark_drawdown"),
        "portfolio_value": round(portfolio_value, 2),
        "portfolio_loss_pct": round(weighted_drawdown * 100, 1),
        "portfolio_loss_amount": round(portfolio_loss_amount, 2),
        "per_asset": per_asset,
        "warnings": warnings,
    }


def compute_historical_stress(
    portfolio: List[Dict[str, Any]],
    dfs_map: Dict[str, pd.DataFrame],
    scenario_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    计算持仓在多个历史压力场景下的预估亏损。

    参数
    ----------
    portfolio : List[Dict]
        持仓列表，每个元素至少包含 code、weight；可选 amount。
    dfs_map : Dict[str, pd.DataFrame]
        股票代码 -> 行情 DataFrame 的映射。
    scenario_ids : List[str], optional
        历史场景 id 列表。为 None 时返回全部预定义历史场景结果。

    返回
    -------
    List[Dict]
        每个历史场景对应的损失结果字典列表。
    """
    portfolio_df = _ensure_portfolio_df(portfolio)
    scenarios = build_scenarios(scenario_ids)

    results = []
    for scenario in scenarios:
        if scenario.type != "historical":
            continue
        results.append(
            calculate_historical_scenario_result(portfolio_df, scenario, dfs_map)
        )

    return results


def list_historical_scenario_names() -> List[str]:
    """返回所有可用的历史压力场景名称。"""
    return [s.name for s in HISTORICAL_SCENARIOS]


def simulate_portfolio_drawdown(
    dfs: List[pd.DataFrame],
    weights: List[float],
    price_col: str = "close",
) -> pd.DataFrame:
    """
    模拟投资组合在历史行情上的累计净值与回撤时间序列。

    采用买入并持有（buy-and-hold）逻辑：将各资产价格归一化到起始日为 1，
    按权重加权得到组合净值，再计算相对历史高点的回撤。

    参数
    ----------
    dfs : List[pd.DataFrame]
        各资产日频行情 DataFrame，需包含 date、code、close 列。
    weights : List[float]
        各资产权重，长度与 dfs 一致，加和应为 1。
    price_col : str, default "close"
        价格列名。

    返回
    -------
    pd.DataFrame
        列包含 date、portfolio_value（累计净值）、drawdown（回撤，负值）。
    """
    if not dfs:
        raise ValueError("dfs cannot be empty")
    if len(dfs) != len(weights):
        raise ValueError("权重数量与资产数量不一致")
    if abs(sum(weights) - 1.0) > 1e-5:
        raise ValueError("权重之和必须等于 1")

    normalized: List[pd.DataFrame] = []
    for i, df in enumerate(dfs):
        if df.empty or price_col not in df.columns or "date" not in df.columns:
            raise ValueError(f"第 {i} 个 DataFrame 缺少必要列或为空")

        df_i = df[["date", price_col]].copy()
        df_i[price_col] = pd.to_numeric(df_i[price_col], errors="coerce")
        df_i = df_i.dropna(subset=[price_col])
        df_i = df_i.sort_values("date").reset_index(drop=True)

        if df_i.empty:
            raise ValueError(f"第 {i} 个 DataFrame 在去除无效价格后为空")

        first_price = df_i[price_col].iloc[0]
        if pd.isna(first_price) or first_price == 0:
            raise ValueError(f"第 {i} 个资产起始价格无效: {first_price}")

        # 归一化到起始日价格为 1，使权重对应实际资金配置比例
        df_i[price_col] = df_i[price_col] / first_price
        normalized.append(df_i)

    merged = normalized[0].rename(columns={price_col: "p0"})
    for i in range(1, len(normalized)):
        df_i = normalized[i].rename(columns={price_col: f"p{i}"})
        merged = merged.merge(df_i, on="date", how="inner")

    merged = merged.sort_values("date").reset_index(drop=True)
    price_cols = [f"p{i}" for i in range(len(normalized))]
    prices = merged[price_cols]

    if prices.empty or len(prices) < 2:
        return pd.DataFrame(columns=["date", "portfolio_value", "drawdown"])

    weights_arr = pd.Series(weights, index=price_cols, dtype=float)
    portfolio_value = (prices * weights_arr).sum(axis=1)
    running_peak = portfolio_value.cummax()
    drawdown = (portfolio_value - running_peak) / running_peak

    return pd.DataFrame({
        "date": merged["date"],
        "portfolio_value": portfolio_value,
        "drawdown": drawdown,
    }).reset_index(drop=True)


# ============================================================================
# 简单使用示例
# ============================================================================
if __name__ == "__main__":
    # 构造一只测试股票：100 -> 120 -> 80，最大回撤约 -33.33%
    dates = pd.date_range("2008-01-01", periods=260, freq="B").strftime("%Y-%m-%d")
    n_up = 130
    prices = [100 + (120 - 100) / n_up * i for i in range(n_up)]
    prices += [120 + (80 - 120) / (len(dates) - n_up) * i for i in range(1, len(dates) - n_up + 1)]
    df_a = pd.DataFrame({
        "date": dates,
        "code": "TEST_A",
        "close": prices,
    })

    print("可用历史场景:", list_historical_scenario_names())

    # 单票最大回撤
    drawdown = calculate_historical_drawdown(
        df_a,
        {"start_date": "2008-01-01", "end_date": "2008-12-31"},
    )
    print(f"TEST_A 最大回撤: {drawdown['max_drawdown'] * 100:.2f}%")

    # 组合在历史场景下的损失
    portfolio = [{"code": "TEST_A", "weight": 1.0, "amount": 100000.0}]
    dfs_map = {"TEST_A": df_a}
    results = compute_historical_stress(portfolio, dfs_map)
    for r in results:
        print(f"  {r['scenario_name']}: {r['portfolio_loss_pct']}%  (基准 {r['benchmark_drawdown']})")
