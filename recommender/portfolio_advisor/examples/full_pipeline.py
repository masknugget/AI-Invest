"""
投资组合诊断 + 风险分析 + 调仓建议 完整链路示例。

用法：
    python research/portfolio_advisor/examples/full_pipeline.py

流程：
    1. 随机抽取 5 只标的并指定权重。
    2. 计算五维诊断得分（drawdown_control / portfolio_diversification /
       position_efficiency / return_stability / style_balance）与综合分。
    3. 基于权重与行业分布生成核心风险提示（调用 LLM）。
    4. 从候选池搜索调仓方案，输出 Top-K 调入/调出建议。

需要在项目根目录下执行，或保证 sys.path 包含项目根目录。
"""

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from infra_structure.models.dao.industry_obj import IndustryQuery

from research.portfolio_advisor.analyst import generate_risks, parse_risks
from research.portfolio_advisor.dimension.run import compute_portfolio_dimensions
from research.portfolio_advisor.rebalance import (
    load_candidate_pool_from_jsonl_as_pool,
    suggest_rebalance,
)


# 候选池文件绝对路径（避免相对路径在不同工作目录下失效）
CANDIDATE_POOL_PATH = Path(r"D:\q_project\quantq\research\portfolio_advisor\data\stock_dimension_scores.jsonl")


def build_industry_distribution(codes: List[str], weights: List[float]) -> Dict[str, float]:
    """
    根据股票代码与权重构建一级行业分布。

    无法查询到行业的股票归入 "未知行业"。
    """
    query = IndustryQuery()
    dist: Dict[str, float] = defaultdict(float)

    for code, weight in zip(codes, weights):
        industry = query.query(code, level="industry_1")
        key = industry if industry else "未知行业"
        dist[key] += weight

    return dict(dist)


def print_dimensions(result) -> None:
    """打印五维诊断结果。"""
    print("\n" + "=" * 70)
    print("【五维诊断结果】")
    print("=" * 70)

    print("【抗回撤能力】")
    print(f"  最大回撤 MDD       : {result.drawdown_control.mdd:.4f}")
    print(f"  控制得分 (0-100)   : {result.drawdown_control.score:.2f}")

    print("\n【资产分散度】")
    print(f"  ENB (weight-based) : {result.portfolio_diversification.enb_weight_based:.4f}")
    print(f"  ENB (risk-based)   : {result.portfolio_diversification.enb_risk_based:.4f}")
    print(f"  分散得分 (0-100)   : {result.portfolio_diversification.score:.2f}")

    print("\n【持仓性价比】")
    print(f"  夏普比率           : {result.position_efficiency.sharpe_ratio:.4f}")
    print(f"  性价比得分 (0-100) : {result.position_efficiency.score:.2f}")

    print("\n【收益稳定性】")
    print(f"  年化波动率         : {result.return_stability.annualized_volatility:.4f}")
    print(f"  稳定得分 (0-100)   : {result.return_stability.score:.2f}")

    print("\n【风格均衡】")
    print(f"  风格 HHI           : {result.style_balance.style_hhi:.4f}")
    print(f"  有效风格数         : {result.style_balance.effective_style_num:.4f}")
    print(f"  均衡得分 (0-100)   : {result.style_balance.score:.2f}")

    print("\n" + "=" * 70)
    print(f"综合健康分 (0-100)    : {result.composite_score:.2f}")
    print(f"几何加权综合分 (0-100) : {result.geometric_composite_score:.2f}")
    print("=" * 70)


def print_risks(weights: List[float], industry_dist: Dict[str, float]) -> None:
    """打印 LLM 生成的核心风险提示。"""
    print("\n" + "=" * 70)
    print("【核心风险提示】")
    print("=" * 70)

    try:
        raw_output = generate_risks(weights, industry_dist)
    except Exception as exc:  # noqa: BLE001
        print(f"调用 LLM 失败（{exc}），跳过风险分析。")
        return

    if raw_output is None:
        print("调用 LLM 失败，未获取到风险提示。")
        return

    risks = parse_risks(raw_output)
    if risks:
        for idx, risk in enumerate(risks, start=1):
            summary = risk.get("summary", "")
            detail = risk.get("detail", "")
            print(f"{idx}. {summary}")
            print(f"   {detail}")
    else:
        print("模型原始输出：")
        print(raw_output)


def print_rebalance_plans(dfs, weights, pool) -> None:
    """打印调仓建议。"""
    print("\n" + "=" * 70)
    print("【调仓建议】")
    print("=" * 70)

    plans = suggest_rebalance(
        dfs,
        weights,
        pool,
        objective="geometric_composite_score",
        max_actions=1,
        top_k=3,
        min_overlap_days=60,
    )

    if not plans:
        print("未找到满足条件的调仓方案。")
        return

    print(f"找到 {len(plans)} 个方案，按几何加权综合分提升降序：\n")
    for idx, plan in enumerate(plans, start=1):
        print(f"方案 {idx}:")
        print(f"  目标         : {plan.objective}")
        print(f"  当前得分     : {plan.score_before:.2f}")
        print(f"  调仓后得分   : {plan.score_after:.2f}")
        print(f"  提升         : {plan.improvement:.2f}")
        for action in plan.actions:
            print(f"  动作         : 调出 {action.code_out}，调入 {action.code_in}")
            print(f"  调入后权重   : {action.weight_in:.4f}")
            print(f"  原因         : {action.reason}")
        print()


def _unwrap_df(item: Any) -> Any:
    """兼容 FileVisitor.iter() 可能返回 (key, df) 元组的情况。"""
    if isinstance(item, tuple):
        return item[1]
    return item


def main() -> None:
    # ------------------------------------------------------------------
    # 1. 构造当前组合：随机 5 只标的 + 权重
    # ------------------------------------------------------------------
    file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

    df_1 = _unwrap_df(file_visitor.random_one())
    df_2 = _unwrap_df(file_visitor.random_one())
    df_3 = _unwrap_df(file_visitor.random_one())
    df_4 = _unwrap_df(file_visitor.random_one())
    df_5 = _unwrap_df(file_visitor.random_one())

    dfs = [df_1, df_2, df_3, df_4, df_5]
    weights = [0.2, 0.3, 0.1, 0.2, 0.2]
    codes = [str(df["code"].iloc[0]) for df in dfs]

    print("=" * 70)
    print("当前组合")
    print("=" * 70)
    print(f"标的: {codes}")
    print(f"权重: {weights}")

    # ------------------------------------------------------------------
    # 2. 五维诊断
    # ------------------------------------------------------------------
    result = compute_portfolio_dimensions(dfs, weights)
    print_dimensions(result)

    # ------------------------------------------------------------------
    # 3. 风险分析
    # ------------------------------------------------------------------
    industry_dist = build_industry_distribution(codes, weights)
    print("\n【行业分布】")
    for industry, ratio in sorted(industry_dist.items(), key=lambda x: -x[1]):
        print(f"  {industry}: {ratio:.2%}")

    print_risks(weights, industry_dist)

    # ------------------------------------------------------------------
    # 4. 调仓建议
    # ------------------------------------------------------------------
    pool = load_candidate_pool_from_jsonl_as_pool(str(CANDIDATE_POOL_PATH))
    print_rebalance_plans(dfs, weights, pool)


if __name__ == "__main__":
    main()
