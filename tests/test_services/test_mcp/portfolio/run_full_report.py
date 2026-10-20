"""
full_report.py 组合全景报告用法示例（真实计算引擎，零 LLM）。

全景报告 = 五维评分 + 风险指标 + 全场景压力测试，依赖行情；
本地已入库代码（sz.000001 等）可真实跑出全景结果。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_full_report.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import full_report


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_full_report():
    banner("示例：portfolio_full_report（五维 + 风险 + 压力测试）")
    try:
        resp = json.loads(
            full_report.portfolio_full_report(["sz.000001", "sz.000002"], [0.5, 0.5])
        )
        print(f"status   -> {resp['status']}")
        print(f"warnings -> {resp.get('warnings')}")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    except Exception as e:
        print("portfolio_full_report 失败 ->", e)


def main():
    demo_full_report()
    print("\n✅ full_report 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
