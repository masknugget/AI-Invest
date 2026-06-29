"""
调仓建议独立示例（增强版）。

用法：
    python research/portfolio_advisor/examples/rebalance_example.py

流程：
    1. 随机抽取 5 只标的并指定权重作为当前组合。
    2. 从 stock_dimension_scores.jsonl 加载候选池（默认前 N 只，避免全量加载卡死）。
    3. 调用 suggest_rebalance 搜索调仓方案。
    4. 打印 Top-K 调入/调出建议。

改进：
    - 使用绝对路径指向候选池，避免工作目录不一致时找不到文件。
    - 复用同一个 FileVisitor 实例，减少重复初始化开销。
    - 默认限制候选池大小，缩短加载与搜索时间。
    - 开启 verbose，实时显示搜索进度。
    - 增加运行耗时统计与友好提示。
"""

import os
import time
from pathlib import Path
from typing import Any

from infra_structure.data_engine.visitor.file_visitor import FileVisitor

from research.portfolio_advisor.rebalance import (
    load_candidate_pool_from_jsonl_as_pool,
    suggest_rebalance,
)


# 候选池文件绝对路径（避免相对路径在不同工作目录下失效）
CANDIDATE_POOL_PATH = Path(r"D:\q_project\quantq\research\portfolio_advisor\data\stock_dimension_scores.jsonl")

# 默认只加载候选池前 N 只股票，避免全量加载导致长时间无响应。
# 可通过环境变量 CANDIDATE_LIMIT 覆盖，例如：set CANDIDATE_LIMIT=50
DEFAULT_CANDIDATE_LIMIT = int(os.environ.get("CANDIDATE_LIMIT", "30"))


def _unwrap_df(item: Any) -> Any:
    """兼容 FileVisitor 可能返回 (key, df) 元组的情况。"""
    if isinstance(item, tuple):
        return item[1]
    return item


def main() -> None:
    start_time = time.time()
    print("=" * 70)
    print("调仓建议独立示例")
    print("=" * 70)

    # 复用同一个 FileVisitor 实例，避免重复初始化
    print("[1/4] 初始化 FileVisitor ...")
    file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

    print("[2/4] 构造当前组合（随机 5 只标的）...")
    current_dfs = [_unwrap_df(file_visitor.random_one()) for _ in range(5)]
    current_weights = [0.2, 0.3, 0.1, 0.2, 0.2]
    current_codes = [str(df["code"].iloc[0]) for df in current_dfs]

    print("-" * 70)
    print("当前组合")
    print("-" * 70)
    print(f"标的: {current_codes}")
    print(f"权重: {current_weights}")

    if not CANDIDATE_POOL_PATH.exists():
        raise FileNotFoundError(f"候选池文件不存在: {CANDIDATE_POOL_PATH}")

    print(
        f"[3/4] 加载候选池（默认前 {DEFAULT_CANDIDATE_LIMIT} 只，"
        "可通过 CANDIDATE_LIMIT 环境变量调整）..."
    )
    pool = load_candidate_pool_from_jsonl_as_pool(
        str(CANDIDATE_POOL_PATH),
        file_visitor=file_visitor,
        limit=DEFAULT_CANDIDATE_LIMIT,
    )
    print(f"实际加载候选数: {len(pool)}")

    if len(pool) == 0:
        print("候选池为空，无法生成调仓建议。")
        return

    print("[4/4] 搜索调仓方案（开启 verbose，可观察进度）...")
    plans = suggest_rebalance(
        current_dfs,
        current_weights,
        pool,
        objective="geometric_composite_score",
        max_actions=1,
        top_k=3,
        min_overlap_days=60,
        verbose=True,
    )

    print("\n" + "=" * 70)
    print("调仓建议")
    print("=" * 70)

    if not plans:
        print("未找到满足条件的调仓方案。")
        return

    for idx, plan in enumerate(plans, start=1):
        print(f"\n方案 {idx}:")
        print(f"  当前得分     : {plan.score_before:.2f}")
        print(f"  调仓后得分   : {plan.score_after:.2f}")
        print(f"  提升         : {plan.improvement:.2f}")
        for action in plan.actions:
            print(f"  调出         : {action.code_out}")
            print(f"  调入         : {action.code_in}")
            print(f"  调入后权重   : {action.weight_in:.4f}")
            print(f"  原因         : {action.reason}")

    elapsed = time.time() - start_time
    print(f"\n总耗时: {elapsed:.2f} 秒")


if __name__ == "__main__":
    main()
