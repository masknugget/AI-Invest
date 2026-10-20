"""
diagnosis.py 五维诊断用法示例（真实数据源，零 LLM）。

演示：
    single_stock_diagnosis   读 p_advisor_cal_dimensions 的预计算结果
    portfolio_diagnosis      组合五维评分（需行情数据）

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_diagnosis.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import diagnosis


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_single_stock():
    banner("示例 1：single_stock_diagnosis（预计算查询）")
    try:
        resp = json.loads(diagnosis.single_stock_diagnosis("000001"))
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:1500])
    except Exception as e:
        print("single_stock_diagnosis 失败 ->", e)


def demo_portfolio():
    banner("示例 2：portfolio_diagnosis（组合五维，需行情）")
    try:
        resp = json.loads(
            diagnosis.portfolio_diagnosis(["sz.000001", "sz.000002"], [0.5, 0.5])
        )
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:1500])
    except Exception as e:
        print("portfolio_diagnosis 失败 ->", e)


def main():
    demo_single_stock()
    demo_portfolio()
    print("\n✅ diagnosis 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
