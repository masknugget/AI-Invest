"""
调仓建议独立示例（增强版）。

用法：
    python recommender/portfolio_advisor/examples/rebalance_example.py

流程：
    1. 从 stock_dimension_scores.jsonl 随机抽取 5 只标的作为当前组合。
    2. 从同一文件加载候选池（默认前 N 只，避免全量加载卡死）。
    3. 调用 suggest_rebalance 搜索调仓方案。
    4. 打印 Top-K 调入/调出建议。

说明：
    本示例完全基于 stock_dimension_scores.jsonl 中的预计算五维得分，不再加载
    行情 DataFrame，因此不再依赖 FileVisitor。
"""

import os
import random
import sys
import time
import types
from pathlib import Path
from typing import List

# 将项目根目录加入路径，使本示例可直接运行
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

# mock openai，避免触发 recommender/__init__.py 中的大量依赖链
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    setattr(_openai_mock, "OpenAI", type("OpenAI", (), {}))
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.rebalance import (
    load_stock_scores_from_jsonl,
    suggest_rebalance,
)


# 候选池文件路径（基于本文件位置推导，避免硬编码绝对路径失效）
SCORES_PATH = Path(__file__).resolve().parent.parent / "data" / "stock_dimension_scores.jsonl"

# 默认只加载候选池前 N 只股票，避免全量加载导致长时间无响应。
# 可通过环境变量 CANDIDATE_LIMIT 覆盖，例如：set CANDIDATE_LIMIT=50
DEFAULT_CANDIDATE_LIMIT = int(os.environ.get("CANDIDATE_LIMIT", "30"))


def _pick_current_codes(all_codes: List[str], n: int = 5) -> List[str]:
    """从所有股票中随机抽取 n 只作为当前组合。"""
    if len(all_codes) < n:
        raise ValueError(f"可选股票数量不足 {n}，当前仅 {len(all_codes)} 只")
    return random.sample(all_codes, n)


def main() -> None:
    start_time = time.time()
    print("=" * 70)
    print("调仓建议独立示例")
    print("=" * 70)

    if not SCORES_PATH.exists():
        raise FileNotFoundError(f"维度得分文件不存在: {SCORES_PATH}")

    print("[1/3] 从 stock_dimension_scores.jsonl 加载所有股票代码...")
    all_scores = load_stock_scores_from_jsonl(str(SCORES_PATH))
    all_codes = list(all_scores.keys())
    print(f"共加载 {len(all_codes)} 只股票")

    print("[2/3] 构造当前组合（随机 5 只标的）...")
    current_codes = _pick_current_codes(all_codes, n=5)
    current_weights = [0.2, 0.3, 0.1, 0.2, 0.2]

    print("-" * 70)
    print("当前组合")
    print("-" * 70)
    print(f"标的: {current_codes}")
    print(f"权重: {current_weights}")

    print(
        f"[3/3] 搜索调仓方案（默认候选前 {DEFAULT_CANDIDATE_LIMIT} 只，"
        "可通过 CANDIDATE_LIMIT 环境变量调整；开启 verbose 观察进度）..."
    )
    plans = suggest_rebalance(
        current_codes=current_codes,
        current_weights=current_weights,
        scores_path=str(SCORES_PATH),
        max_actions=1,
        top_k=3,
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
