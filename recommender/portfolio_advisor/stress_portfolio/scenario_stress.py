"""
宏观情景压力测试

设计原则：
- 纯函数，无模块级 I/O（不直接实例化 FileVisitor / IndustryQuery）
- 一个“情景”可以同时对多个板块/行业施加不同的收益率冲击
- 与 sector_stress.py 的区别：
    - sector_stress.py 针对单一板块回调；
    - scenario_stress.py 面向宏观事件，一次性影响多个板块。

使用示例：
    from research.portfolio_advisor.stress_portfolio.scenario_stress import (
        calculate_scenario_stress_result,
        compute_scenario_stress,
    )

    portfolio = [
        {"code": "A", "weight": 0.4, "amount": 40000},
        {"code": "B", "weight": 0.6, "amount": 60000},
    ]
    result = compute_scenario_stress(
        portfolio,
        "美联储加息",
        industry_lookup=lambda c: "电子" if c == "A" else "银行",
    )
"""

from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from recommender.portfolio_advisor.stress_portfolio.const import (
    SW_INDUSTRY_TO_SECTOR,
)


# ============================================================================
# 预定义宏观情景：板块 -> 预期收益率冲击
# 例如：美联储加息通常对高估值科技板块冲击更大，对金融板块偏正面
# ============================================================================
DEFAULT_SCENARIO_SHOCKS = {
    "美联储加息": {
        "科技": -0.15,
        "医药": -0.05,
        "金融": 0.03,
        "消费": -0.08,
        "周期": -0.10,
    },
    "通胀上行": {
        "科技": -0.10,
        "医药": -0.02,
        "金融": 0.05,
        "消费": -0.06,
        "周期": 0.08,
    },
    "经济衰退": {
        "科技": -0.20,
        "医药": -0.03,
        "金融": -0.15,
        "消费": -0.12,
        "周期": -0.18,
    },
}


def _lookup_industry(
    industry_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> Callable[[str], Optional[str]]:
    """返回行业查询函数。未提供时使用硬编码的 mock 映射。"""
    if industry_lookup is not None:
        return industry_lookup

    _mock_industry_map: Dict[str, str] = {
        "600519": "食品饮料",
        "000858": "食品饮料",
        "000001": "银行",
        "600036": "银行",
        "601318": "非银金融",
        "000333": "家用电器",
        "002594": "汽车",
        "300750": "电气设备",
        "000725": "电子",
        "600276": "医药生物",
    }

    def _query(code: str) -> Optional[str]:
        return _mock_industry_map.get(code)

    return _query


def calculate_scenario_stress_result(
    portfolio_df: pd.DataFrame,
    scenario_shocks: Dict[str, float],
    industry_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    计算一个宏观情景对组合的冲击。

    参数
    ----------
    portfolio_df : pd.DataFrame
        包含 code、weight、amount 的持仓数据。
    scenario_shocks : Dict[str, float]
        板块桶 -> 预期收益率冲击（例如 {"科技": -0.15}）。
    industry_lookup : Callable[[str], Optional[str]], optional
        股票代码 -> 申万一级行业名称。未提供时延迟构造 IndustryQuery。

    返回
    -------
    dict
        含 scenario_name、portfolio_loss_pct、portfolio_loss_amount、
        per_asset、affected_stocks、warnings 的字典。
    """
    lookup = _lookup_industry(industry_lookup)

    portfolio_df = portfolio_df.copy()
    if "industry" not in portfolio_df.columns:
        portfolio_df["industry"] = portfolio_df["code"].apply(lookup)

    portfolio_df["sector_bucket"] = portfolio_df["industry"].map(SW_INDUSTRY_TO_SECTOR)
    portfolio_df["stress_return"] = portfolio_df["sector_bucket"].map(scenario_shocks).fillna(0.0)

    # 按权重加权得到组合层面损失
    portfolio_loss = float((portfolio_df["weight"] * portfolio_df["stress_return"]).sum())
    portfolio_value = float(portfolio_df["amount"].sum())

    # 逐票明细
    per_asset = []
    for _, row in portfolio_df.iterrows():
        stress_return = float(row["stress_return"])
        weight = float(row["weight"])
        amount = float(row["amount"])
        per_asset.append({
            "code": row["code"],
            "weight": weight,
            "amount": amount,
            "sector": row.get("sector_bucket"),
            "industry": row.get("industry"),
            "stress_return": stress_return,
            "loss_amount": amount * stress_return,
        })

    # 收集 warnings
    warnings = []
    missing_industry_mask = portfolio_df["industry"].isna()
    if missing_industry_mask.any():
        missing_codes = portfolio_df.loc[missing_industry_mask, "code"].tolist()
        warnings.append(f"以下持仓代码无法识别行业，未纳入情景压力测试：{missing_codes}")

    affected_mask = portfolio_df["stress_return"] != 0.0
    affected_stocks = portfolio_df.loc[affected_mask, "code"].tolist()

    return {
        "scenario_name": "自定义宏观情景",
        "portfolio_loss_pct": round(portfolio_loss * 100, 2),
        "portfolio_loss_amount": round(portfolio_loss * portfolio_value, 2),
        "per_asset": per_asset,
        "affected_stocks": affected_stocks,
        "warnings": warnings,
    }


def compute_scenario_stress(
    portfolio: List[Dict[str, Any]],
    scenario_name: str,
    industry_lookup: Optional[Callable[[str], Optional[str]]] = None,
    scenarios: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    根据预定义或自定义的宏观情景名称，计算组合损失。

    参数
    ----------
    portfolio : List[Dict]
        持仓列表，每个元素至少包含 code、weight；可选 amount。
    scenario_name : str
        情景名称，需在 scenarios 中存在。
    industry_lookup : Callable[[str], Optional[str]], optional
        行业查询函数。
    scenarios : Dict[str, Dict[str, float]], optional
        自定义情景库。未提供时使用 DEFAULT_SCENARIO_SHOCKS。

    返回
    -------
    dict
        损失结果字典。
    """
    scenario_lib = scenarios if scenarios is not None else DEFAULT_SCENARIO_SHOCKS
    if scenario_name not in scenario_lib:
        raise ValueError(
            f"未知情景：{scenario_name}。可用情景：{list(scenario_lib.keys())}"
        )

    portfolio_df = pd.DataFrame(portfolio)
    if "amount" not in portfolio_df.columns:
        portfolio_df["amount"] = portfolio_df["weight"]

    result = calculate_scenario_stress_result(
        portfolio_df,
        scenario_lib[scenario_name],
        industry_lookup=industry_lookup,
    )
    result["scenario_name"] = scenario_name
    return result


def list_scenario_names(scenarios: Optional[Dict[str, Dict[str, float]]] = None) -> List[str]:
    """返回可用宏观情景名称列表。"""
    scenario_lib = scenarios if scenarios is not None else DEFAULT_SCENARIO_SHOCKS
    return list(scenario_lib.keys())


# ============================================================================
# 简单使用示例
# ============================================================================
if __name__ == "__main__":
    portfolio = [
        {"code": "A", "weight": 0.4, "amount": 40000.0},
        {"code": "B", "weight": 0.6, "amount": 60000.0},
    ]

    def _stub_lookup(code: str) -> Optional[str]:
        return {"A": "电子", "B": "银行"}.get(code)

    print("可用宏观情景:", list_scenario_names())
    for name in list_scenario_names():
        result = compute_scenario_stress(portfolio, name, industry_lookup=_stub_lookup)
        print("-" * 50)
        print(f"情景: {result['scenario_name']}")
        print(f"组合损失: {result['portfolio_loss_pct']}%")
        print(f"损失金额: {result['portfolio_loss_amount']}")
        print(f"受影响股票: {result['affected_stocks']}")
        if result["warnings"]:
            print(f"warnings: {result['warnings']}")
