"""
rebalance.py 调仓建议用法示例（真实计算引擎，零 LLM）。

候选池与当前组合得分均从 MongoDB p_advisor_cal_dimensions 读取（代码格式为
baostock 风格 sh.600000 等），示例展示：
    objective="composite_score"  单动作、Top-3 方案
    objective="drawdown_control" 抗回撤目标

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_rebalance.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import rebalance

CODES = ["000001", "000002"]
WEIGHTS = [0.5, 0.5]


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_objective(objective: str) -> None:
    banner(f"示例：portfolio_rebalance_suggestion(objective={objective!r})")
    try:
        resp = json.loads(
            rebalance.portfolio_rebalance_suggestion(
                CODES, WEIGHTS, objective=objective, max_actions=1, top_k=3
            )
        )
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:1500])
    except Exception as e:
        print(f"portfolio_rebalance_suggestion({objective}) 失败 -> {e}")


def main():
    demo_objective("composite_score")
    demo_objective("drawdown_control")
    print("\n✅ rebalance 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
