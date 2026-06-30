"""
sector_stress.py 使用示例与简单校验。

运行方式：
    python recommender/portfolio_advisor/test/test_stress/t_sector_stress.py
"""

import sys
import types

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    _openai_mock.OpenAI = type("OpenAI", (), {})
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
    calculate_sector_stress_result,
    compute_sector_stress,
    list_sector_names,
)
from recommender.portfolio_advisor.stress_portfolio.const import SECTOR_BETAS


# ---------------------------------------------------------------------------
# Stub: 股票代码 -> 申万一级行业
# ---------------------------------------------------------------------------
def _stub_lookup(code: str):
    return {
        "TECH_A": "电子",
        "TECH_B": "计算机",
        "FIN_A": "银行",
        "FIN_B": "非银金融",
        "PHA_A": "医药生物",
        "UNK": "未知行业",
    }.get(code)


# ---------------------------------------------------------------------------
# 1. 查看可用板块
# ---------------------------------------------------------------------------
print("=" * 60)
print("可用板块")
print("=" * 60)
sectors = list_sector_names()
print(f"板块列表: {sectors}")
print(f"Beta 映射: {dict(SECTOR_BETAS)}")

# ---------------------------------------------------------------------------
# 2. 基本用法：科技板块回调 20%
# ---------------------------------------------------------------------------
print("=" * 60)
print("科技板块回调 20%")
print("=" * 60)

portfolio = [
    {"code": "TECH_A", "weight": 0.4, "amount": 40000},
    {"code": "TECH_B", "weight": 0.3, "amount": 30000},
    {"code": "FIN_A", "weight": 0.3, "amount": 30000},
]

result = compute_sector_stress(
    portfolio,
    sector="科技",
    sector_callback_pct=0.20,
    industry_lookup=_stub_lookup,
)
print(f"场景          : {result['scenario']}")
print(f"Beta          : {result['beta']}")
print(f"组合损失      : {result['portfolio_loss_pct']}%")
print(f"损失金额      : {result['portfolio_loss_amount']}")
print(f"受影响股票    : {result['affected_stocks']}")
print(f"逐票明细:")
for a in result["per_asset"]:
    print(f"  {a['code']}  行业={a['industry']}  板块={a['sector_bucket']}  "
          f"压力收益={a['stress_return']:.2%}  损失={a['loss_amount']:.0f}")

# ---------------------------------------------------------------------------
# 3. 金融板块回调 15%
# ---------------------------------------------------------------------------
print("=" * 60)
print("金融板块回调 15%")
print("=" * 60)

result_fin = compute_sector_stress(
    portfolio,
    sector="金融",
    sector_callback_pct=0.15,
    industry_lookup=_stub_lookup,
)
print(f"场景          : {result_fin['scenario']}")
print(f"组合损失      : {result_fin['portfolio_loss_pct']}%")
print(f"受影响股票    : {result_fin['affected_stocks']}")

# ---------------------------------------------------------------------------
# 4. 无法识别行业的股票 -> warnings
# ---------------------------------------------------------------------------
print("=" * 60)
print("行业缺失时的 warnings")
print("=" * 60)

portfolio_with_unknown = [
    {"code": "TECH_A", "weight": 0.5, "amount": 50000},
    {"code": "UNK", "weight": 0.5, "amount": 50000},
]
result_unk = compute_sector_stress(
    portfolio_with_unknown,
    sector="科技",
    sector_callback_pct=0.20,
    industry_lookup=_stub_lookup,
)
print(f"warnings: {result_unk['warnings']}")

# ---------------------------------------------------------------------------
# 5. 无效板块 -> ValueError
# ---------------------------------------------------------------------------
print("=" * 60)
print("无效板块校验")
print("=" * 60)

try:
    compute_sector_stress(portfolio, sector="不存在的板块", industry_lookup=_stub_lookup)
    print("ERROR: 应抛出 ValueError")
except ValueError as e:
    print(f"ValueError: {e}")

# ---------------------------------------------------------------------------
# 6. 可选：用本地 parquet 数据跑一次
# ---------------------------------------------------------------------------
print("=" * 60)
print("本地真实数据示例")
print("=" * 60)

try:
    from recommender.portfolio_advisor.data_read import load_all

    data = load_all()
    dfs = [data["df_1"], data["df_2"], data["df_3"]]
    real_portfolio = [
        {"code": str(df["code"].iloc[0]), "weight": w, "amount": w * 100000}
        for df, w in zip(dfs, [0.4, 0.3, 0.3])
    ]

    result_real = compute_sector_stress(real_portfolio, sector="科技")
    print(f"场景          : {result_real['scenario']}")
    print(f"组合损失      : {result_real['portfolio_loss_pct']}%")
    print(f"受影响股票    : {result_real['affected_stocks']}")
    if result_real["warnings"]:
        print(f"warnings      : {result_real['warnings']}")
except Exception as exc:  # noqa: BLE001
    print(f"  本地数据示例跳过（环境依赖不满足）: {exc}")

print("=" * 60)
print("t_sector_stress.py 运行完成")
print("=" * 60)
