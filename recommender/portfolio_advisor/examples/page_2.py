from typing import Any, List

from pathlib import Path
import os
import sys
import types
import pandas as pd

# 将项目根目录加入 sys.path，确保能导入 recommender 等模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    setattr(_openai_mock, "OpenAI", type("OpenAI", (), {}))
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions


def _unwrap_df(item: Any) -> Any:
    """兼容 FileVisitor 可能返回 (key, df) 元组的情况。"""
    if isinstance(item, tuple):
        return item[1]
    return item



DATA_DIR = Path(r'F:\project_work\hf\AI-Invest\recommender\portfolio_advisor\data')

def _read_parquet(filename: str) -> pd.DataFrame:
    """读取单个 parquet 文件，文件不存在时抛出 FileNotFoundError。"""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    return pd.read_parquet(path)

# 模块级变量：df_1 ~ df_5
df_1 = _read_parquet("df_1.parquet")
df_2 = _read_parquet("df_2.parquet")
df_3 = _read_parquet("df_3.parquet")

dfs = [df_1, df_2, df_3]
weights = [0.3, 0.3, 0.4]


# ============================================================
# 压力测试：基于 stress_portfolio 模块
# ============================================================
from recommender.portfolio_advisor.stress_portfolio.history_stress import (
    compute_historical_stress,
    simulate_portfolio_drawdown,
)
from recommender.portfolio_advisor.stress_portfolio.scenario_stress import compute_scenario_stress
from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
    compute_sector_stress,
    list_sector_names,
)

# 构造持仓列表与行情映射
codes = [str(df["code"].iloc[0]) for df in dfs]
portfolio = [{"code": code, "weight": w, "amount": w * 100000.0} for code, w in zip(codes, weights)]
dfs_map = {code: df for code, df in zip(codes, dfs)}

print("\n" + "=" * 70)
print("【压力测试】")
print("=" * 70)

# 1. 历史极端行情压力测试
print("\n--- 历史极端行情压力测试 ---")
historical_results = compute_historical_stress(portfolio, dfs_map)
if historical_results:
    for r in historical_results:
        print(f"场景: {r['scenario_name']} ({r['start_date']} ~ {r['end_date']})")
        print(f"  组合损失: {r['portfolio_loss_pct']}%")
        print(f"  损失金额: {r['portfolio_loss_amount']}")
        print(f"  基准回撤: {r['benchmark_drawdown']}")
else:
    print("无历史压力测试结果。")

# 2. 板块压力测试
print("\n--- 板块压力测试 ---")
for sector in list_sector_names():
    r = compute_sector_stress(portfolio, sector=sector, sector_callback_pct=0.20)
    print(f"场景: {r['scenario']}")
    print(f"  组合损失: {r['portfolio_loss_pct']}%")
    print(f"  受影响股票: {r['affected_stocks']}")
    if r["warnings"]:
        print(f"  警告: {r['warnings']}")

# 3. 宏观情景压力测试
print("\n--- 宏观情景压力测试 ---")
for scenario_name in ["美联储加息", "通胀上行", "经济衰退"]:
    r = compute_scenario_stress(portfolio, scenario_name=scenario_name)
    print(f"情景: {r['scenario_name']}")
    print(f"  组合损失: {r['portfolio_loss_pct']}%")
    print(f"  受影响股票: {r['affected_stocks']}")
    if r["warnings"]:
        print(f"  警告: {r['warnings']}")

# 4. 组合净值与回撤时间序列模拟
print("\n--- 组合净值回撤模拟 ---")
drawdown_df = simulate_portfolio_drawdown(dfs, weights)
if not drawdown_df.empty:
    max_drawdown = drawdown_df["drawdown"].min()
    print(f"历史最大回撤: {max_drawdown * 100:.2f}%")
    print(f"最新净值: {drawdown_df['portfolio_value'].iloc[-1]:.4f}")
    print(f"数据区间: {drawdown_df['date'].iloc[0]} ~ {drawdown_df['date'].iloc[-1]}")
else:
    print("无法计算组合净值回撤。")


# ============================================================
# 调仓建议：基于 rebalance 模块
# ============================================================
from recommender.portfolio_advisor.rebalance import (
    load_candidate_pool_from_jsonl_as_pool,
    suggest_rebalance,
)

CANDIDATE_POOL_PATH = Path(__file__).resolve().parent.parent / "data" / "stock_dimension_scores.jsonl"
DEFAULT_CANDIDATE_LIMIT = int(os.environ.get("CANDIDATE_LIMIT", "30"))

print("\n" + "=" * 70)
print("【调仓建议】")
print("=" * 70)
if not CANDIDATE_POOL_PATH.exists():
    print(f"候选池文件不存在: {CANDIDATE_POOL_PATH}")
else:
    try:
        pool = load_candidate_pool_from_jsonl_as_pool(
            str(CANDIDATE_POOL_PATH),
            limit=DEFAULT_CANDIDATE_LIMIT,
        )
    except Exception as e:
        print(f"通过 FileVisitor 加载候选池失败（{e}），使用当前组合数据构造示例候选池。")
        from recommender.portfolio_advisor.rebalance import CandidatePool, StockCandidate
        pool = CandidatePool(candidates=[
            StockCandidate(code=f"CAND_{i}", df=df.copy(), dimension_scores={})
            for i, df in enumerate(dfs)
        ])

    print(f"实际加载候选数: {len(pool)}")

    if len(pool) == 0:
        print("候选池为空，无法生成调仓建议。")
    else:
        plans = suggest_rebalance(
            dfs,
            weights,
            pool,
            objective="geometric_composite_score",
            max_actions=1,
            top_k=3,
            min_overlap_days=60,
            verbose=False,
        )

        if not plans:
            print("未找到满足条件的调仓方案。")
        else:
            print(f"找到 {len(plans)} 个方案，按几何加权综合分提升降序：\n")
            for idx, plan in enumerate(plans, start=1):
                print(f"方案 {idx}:")
                print(f"  目标         : {plan.objective}")
                print(f"  当前得分     : {plan.score_before:.2f}")
                print(f"  调仓后得分   : {plan.score_after:.2f}")
                print(f"  提升         : {plan.improvement:.2f}")
                for action in plan.actions:
                    print(f"  调出         : {action.code_out}")
                    print(f"  调入         : {action.code_in}")
                    print(f"  调入后权重   : {action.weight_in:.4f}")
                    print(f"  原因         : {action.reason}")
                print()


