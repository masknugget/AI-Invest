"""
板块压力测试 —— 单一板块回调模拟（对应 FR-002）

设计原则：
- 纯函数，无模块级 I/O（不直接实例化 FileVisitor / IndustryQuery）
- 仅负责单一板块整体回调场景下的组合损失模拟
- 返回普通 dict，便于上层 stress_test.py 包装为 dataclass
- 与 scenario_stress.py 的区别：
    - sector_stress.py 针对单一板块回调（如"科技板块回调20%"）；
    - scenario_stress.py 面向宏观事件，一次性影响多个板块。

核心公式：
    基金回撤 = 板块回调幅度 × Beta
    组合损失 = Σ(各基金持仓权重 × 该基金的压力收益率)

使用示例：
    from research.portfolio_advisor.stress_portfolio.sector_stress import (
        calculate_sector_stress_result,
        compute_sector_stress,
    )

    portfolio = [
        {"code": "A", "weight": 0.4, "amount": 40000},
        {"code": "B", "weight": 0.6, "amount": 60000},
    ]
    result = compute_sector_stress(
        portfolio,
        sector="科技",
        sector_callback_pct=0.20,
        industry_lookup=lambda c: "电子" if c == "A" else "银行",
    )
"""

from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from recommender.portfolio_advisor.stress_portfolio.const import (
    DEFAULT_SECTOR_CALLBACK_PCT,
    SECTOR_BETAS,
    SW_INDUSTRY_TO_SECTOR,
)


# ============================================================================
# 私有辅助函数
# ============================================================================
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


# ============================================================================
# 核心计算函数
# ============================================================================
def calculate_sector_stress_result(
    portfolio_df: pd.DataFrame,
    sector: str = "科技",
    sector_callback_pct: float = DEFAULT_SECTOR_CALLBACK_PCT,
    industry_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    计算单一板块整体回调时对组合的冲击。

    核心逻辑：
    1. 查询每只股票的申万一级行业
    2. 将行业映射到板块桶（科技/医药/金融/消费/周期）
    3. 命中目标板块的股票：压力收益率 = -回调幅度 × Beta
    4. 未命中目标板块的股票：压力收益率 = 0
    5. 组合损失 = Σ(权重 × 压力收益率)

    参数
    ----------
    portfolio_df : pd.DataFrame
        包含 code、weight、amount 的持仓数据。
    sector : str, default "科技"
        目标板块桶，需在 SECTOR_BETAS 中定义。
    sector_callback_pct : float, default 0.20
        板块回调幅度，例如 0.20 表示回调 20%。
    industry_lookup : Callable[[str], Optional[str]], optional
        股票代码 -> 申万一级行业名称。未提供时延迟构造 IndustryQuery。

    返回
    -------
    dict
        {
            "scenario": 场景名称,
            "sector": 板块桶名,
            "sector_callback_pct": 回调幅度,
            "beta": 使用的 Beta 系数,
            "portfolio_loss_pct": 组合损失百分比（保留 2 位小数，负数）,
            "portfolio_loss_amount": 组合损失金额,
            "per_asset": 逐票明细列表,
            "affected_stocks": 受影响股票代码列表,
            "warnings": 警告信息,
        }
    """
    if sector not in SECTOR_BETAS:
        raise ValueError(
            f"未知板块桶：{sector}。支持的板块：{list(SECTOR_BETAS.keys())}"
        )

    lookup = _lookup_industry(industry_lookup)

    # 查询行业
    portfolio_df = portfolio_df.copy()
    if "industry" not in portfolio_df.columns:
        portfolio_df["industry"] = portfolio_df["code"].apply(lookup)

    # 将申万一级行业映射到板块桶
    portfolio_df["sector_bucket"] = portfolio_df["industry"].map(SW_INDUSTRY_TO_SECTOR)

    # 命中目标板块的股票
    sector_mask = portfolio_df["sector_bucket"] == sector

    # 计算每只股票的压力收益
    beta = SECTOR_BETAS[sector]
    portfolio_df["stress_return"] = 0.0
    portfolio_df.loc[sector_mask, "stress_return"] = -sector_callback_pct * beta

    # 组合层面损失（按权重加权）
    portfolio_loss = float((portfolio_df["weight"] * portfolio_df["stress_return"]).sum())
    portfolio_value = float(portfolio_df["amount"].sum()) if "amount" in portfolio_df.columns else None

    # 逐票明细
    per_asset = []
    for _, row in portfolio_df.iterrows():
        stress_return = float(row["stress_return"])
        weight = float(row["weight"])
        amount = float(row["amount"]) if "amount" in row else 0.0
        per_asset.append({
            "code": row["code"],
            "weight": weight,
            "amount": amount,
            "industry": row.get("industry"),
            "sector_bucket": row.get("sector_bucket"),
            "stress_return": stress_return,
            "loss_amount": amount * stress_return,
        })

    # 收集 warnings
    warnings = []
    missing_industry_mask = portfolio_df["industry"].isna()
    if missing_industry_mask.any():
        missing_codes = portfolio_df.loc[missing_industry_mask, "code"].tolist()
        warnings.append(
            f"以下持仓代码无法识别行业，未纳入板块压力测试：{missing_codes}"
        )

    affected_stocks = portfolio_df.loc[sector_mask, "code"].tolist()

    return {
        "scenario": f"{sector}板块整体回调{sector_callback_pct * 100:.0f}%",
        "sector": sector,
        "sector_callback_pct": sector_callback_pct,
        "beta": beta,
        "portfolio_loss_pct": round(portfolio_loss * 100, 2),
        "portfolio_loss_amount": round(portfolio_loss * portfolio_value, 2)
        if portfolio_value is not None
        else None,
        "per_asset": per_asset,
        "affected_stocks": affected_stocks,
        "warnings": warnings,
    }


def compute_sector_stress(
    portfolio: List[Dict[str, Any]],
    sector: str = "科技",
    sector_callback_pct: float = DEFAULT_SECTOR_CALLBACK_PCT,
    industry_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    计算持仓在单一板块回调场景下的预估亏损。

    参数
    ----------
    portfolio : List[Dict]
        持仓列表，每个元素至少包含 code、weight；可选 amount。
    sector : str, default "科技"
        目标板块桶。
    sector_callback_pct : float, default 0.20
        板块回调幅度。
    industry_lookup : Callable[[str], Optional[str]], optional
        行业查询函数。

    返回
    -------
    dict
        损失结果字典。
    """
    portfolio_df = pd.DataFrame(portfolio)
    if "amount" not in portfolio_df.columns:
        portfolio_df["amount"] = portfolio_df["weight"]

    return calculate_sector_stress_result(
        portfolio_df,
        sector=sector,
        sector_callback_pct=sector_callback_pct,
        industry_lookup=industry_lookup,
    )


def list_sector_names() -> List[str]:
    """返回所有可用的板块桶名称。"""
    return list(SECTOR_BETAS.keys())


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

    print("可用板块:", list_sector_names())
    for sector_name in list_sector_names():
        result = compute_sector_stress(
            portfolio,
            sector=sector_name,
            sector_callback_pct=0.20,
            industry_lookup=_stub_lookup,
        )
        print("-" * 50)
        print(f"场景: {result['scenario']}")
        print(f"Beta: {result['beta']}")
        print(f"组合损失: {result['portfolio_loss_pct']}%")
        print(f"损失金额: {result['portfolio_loss_amount']}")
        print(f"受影响股票: {result['affected_stocks']}")
        if result["warnings"]:
            print(f"warnings: {result['warnings']}")
