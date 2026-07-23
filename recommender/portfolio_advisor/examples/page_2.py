from typing import Any, List

import json

from pathlib import Path
import pandas as pd

from app.core.db import save_advisor_result
from app.core.db.p_advisor import (
    save_rebalance_plans,
    get_rebalance_plans,
    save_stress_report,
    get_stress_report,
)
from recommender.news_reader.llms import chat_once
from recommender.portfolio_advisor.analyst import parse_risks, generate_risks, prompt_comprehensive
from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions
from recommender.portfolio_advisor.format_adapt.format_rebalance import format_rebalance_plans
from recommender.portfolio_advisor.rebalance import (
    load_stock_scores_from_jsonl,
    suggest_rebalance,
)
from recommender.portfolio_advisor.format_adapt.format_stress import (
    format_all_stress_reports,
    format_macro_reports,
    format_sector_reports,
    format_stress_reports,
    format_stress_scenario,
)
from recommender.portfolio_advisor.rebalance.loader import load_code_name_from_jsonl
from recommender.portfolio_advisor.stress_portfolio.history_stress import (
    compute_historical_stress,
    list_historical_scenario_names,
    simulate_portfolio_drawdown,
)
from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
    compute_scenario_stress,
    list_scenario_names as list_macro_scenario_names,
)
from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
    compute_sector_stress,
    list_sector_names,
)


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
# codes = [str(df["code"].iloc[0]) for df in dfs]
codes = ["sh.600008", "sh.600009", "sh.600010"]
names = ["首创环保", "上海机场", "包钢股份"]

industry_data = {
    "sh.600008": "Natural Gas Utilities",
    "sh.600009": "Specialty Retailers",
    "sh.600010": "Specialty Retailers",
}

# 核心风险提示
sample_industry = {
    "Specialty Retailers": 0.7,
    "Natural Gas Utilities": 0.3,
}

user_id = "admin123"

# 构造压力测试所需的持仓与行情映射
portfolio = [
    {"code": code, "weight": weight, "amount": weight}
    for code, weight in zip(codes, weights)
]
dfs_map = {code: df for code, df in zip(codes, dfs)}

# 简单行业映射（无实际行业查询时供板块/情景压力测试使用）
_industry_lookup = {
    "sz.300005": "医药生物",
    "sz.300291": "电子",
    "sh.601689": "汽车",
}.get

print("=" * 70)
print("压力测试")
print("=" * 70)

# 历史极端行情压力测试
print("\n【历史极端行情压力测试】")
print("可用历史场景:", list_historical_scenario_names())
hist_results = compute_historical_stress(portfolio, dfs_map)
for r in hist_results:
    print(f"  {r['scenario_name']}: 组合损失 {r['portfolio_loss_pct']}%  (基准 {r['benchmark_drawdown']})")
    if r["warnings"]:
        for w in r["warnings"]:
            print(f"    warning: {w}")

# 格式化为前端展示格式
print("\n【历史极端行情压力测试 - 格式化输出】")
formatted_stress = format_stress_reports(hist_results)
for item in formatted_stress:
    print(json.dumps(item, ensure_ascii=False, indent=2))

# 宏观情景压力测试
print("\n【宏观情景压力测试】")
print("可用宏观情景:", list_macro_scenario_names())
macro_results = []
for scenario_name in list_macro_scenario_names():
    r = compute_scenario_stress(
        portfolio, scenario_name, industry_lookup=_industry_lookup
    )
    macro_results.append(r)
    print(f"  {r['scenario_name']}: 组合损失 {r['portfolio_loss_pct']}%")
    if r["warnings"]:
        for w in r["warnings"]:
            print(f"    warning: {w}")

# 格式化为前端展示格式
print("\n【宏观情景压力测试 - 格式化输出】")
for item in format_macro_reports(macro_results):
    print(json.dumps(item, ensure_ascii=False, indent=2))

# 板块压力测试
print("\n【板块压力测试】")
print("可用板块:", list_sector_names())
sector_results = []
for sector_name in list_sector_names():
    r = compute_sector_stress(
        portfolio,
        sector=sector_name,
        sector_callback_pct=0.20,
        industry_lookup=_industry_lookup,
    )
    sector_results.append(r)
    print(f"  {r['scenario']}: 组合损失 {r['portfolio_loss_pct']}%")
    if r["warnings"]:
        for w in r["warnings"]:
            print(f"    warning: {w}")

# 格式化为前端展示格式
print("\n【板块压力测试 - 格式化输出】")
for item in format_sector_reports(sector_results):
    print(json.dumps(item, ensure_ascii=False, indent=2))

# 组合历史净值与回撤时间序列模拟
print("\n【组合历史净值与回撤模拟】")
drawdown_df = simulate_portfolio_drawdown(dfs, weights)
print(drawdown_df.tail())
print(f"  最新组合净值: {drawdown_df['portfolio_value'].iloc[-1]:.4f}")
print(f"  最新回撤: {drawdown_df['drawdown'].iloc[-1] * 100:.2f}%")

# 保存格式化后的压力测试报告
print("\n【保存格式化压力测试报告】")
output_path = DATA_DIR / "formatted_stress_report.json"
full_report = format_all_stress_reports(hist_results, macro_results, sector_results)
with output_path.open("w", encoding="utf-8") as f:
    json.dump(full_report, f, ensure_ascii=False, indent=2)
print(f"  已保存到: {output_path}")

# 保存压力测试综合报告到 MongoDB
save_stress_report(full_report, user_id=user_id)
print(f"  已保存到 MongoDB，user_id={user_id}")

# 查询并展示最新的压力测试报告
print("\n【查询最新压力测试报告】")
latest_report = get_stress_report(user_id=user_id)
if latest_report:
    print(f"  报告包含 {len(latest_report)} 个字段")
else:
    print("  未找到历史压力测试报告")

# 单独格式化首个历史场景（与 format_stress_reports 等价）
print("\n【首个场景单独格式化】")
first_formatted = format_stress_scenario(hist_results[0], hist_results)
print(json.dumps(first_formatted, ensure_ascii=False, indent=2))

# 调仓建议：确定组合的调入与调出
print("\n" + "=" * 70)
print("调仓建议")
print("=" * 70)

CANDIDATE_POOL_PATH = DATA_DIR / "stock_dimension_scores.jsonl"
if CANDIDATE_POOL_PATH.exists():
    print(f"候选池数量: 从 {CANDIDATE_POOL_PATH} 加载")
    # 加载所有股票的五维评分，供 LLM 原因生成使用
    all_scores = load_stock_scores_from_jsonl(str(CANDIDATE_POOL_PATH))

    code_name = load_code_name_from_jsonl(str(CANDIDATE_POOL_PATH))
    if len(codes) > 0:
        plans = suggest_rebalance(
            current_codes=codes,
            current_weights=weights,
            scores_path=str(CANDIDATE_POOL_PATH),
            max_actions=1,
            top_k=3,
            verbose=False,
        )

        if not plans:
            print("未找到满足条件的调仓方案。")
        else:
            formatted_plans = format_rebalance_plans(
                plans,
                all_scores,
                current_codes=codes,
                current_weights=weights,
                include_llm_reason=True,
            )

            # 为每个调仓动作补充股票名称（调入/调出）
            for plan in formatted_plans:
                for action in plan.get("actions", []):
                    code_in = action.get("code_in")
                    code_out = action.get("code_out")
                    if code_in:
                        action["name_in"] = code_name.get(code_in)
                    if code_out:
                        action["name_out"] = code_name.get(code_out)

            # 保存调仓方案到 MongoDB
            save_rebalance_plans(formatted_plans, user_id=user_id)
            print(f"\n已保存调仓方案到 MongoDB，user_id={user_id}")

            for plan_dict in formatted_plans:
                print(f"\n方案:")
                print(json.dumps(plan_dict, ensure_ascii=False, indent=2))

            # 查询并展示最新的调仓方案
            print("\n【查询最新调仓方案】")
            latest_plans = get_rebalance_plans(user_id=user_id)
            if latest_plans:
                print(f"  共 {len(latest_plans)} 个方案")
            else:
                print("  未找到历史调仓方案")
    else:
        print("当前组合为空，跳过调仓建议。")
else:
    print(f"候选池文件不存在，跳过调仓建议: {CANDIDATE_POOL_PATH}")
