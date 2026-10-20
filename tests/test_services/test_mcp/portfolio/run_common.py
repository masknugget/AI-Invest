"""
_common.py 契约层用法示例（纯函数，无 I/O，离线即可运行）。

演示 MCP 公共工具的能力，直接调用并打印结果，无断言：
    validate_portfolio      校验并归一化组合参数
    build_portfolio_arg     构造压测引擎入参
    make_response           统一响应封装

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_common.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import _common


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_validate_portfolio():
    banner("示例 1：validate_portfolio（校验并归一化权重）")
    codes, weights = _common.validate_portfolio(["sh.600000", "sh.600004"], [1, 1])
    print("codes   ->", codes)
    print("weights ->", weights, "sum=", sum(weights))

    try:
        _common.validate_portfolio([], [])
    except ValueError as e:
        print("空组合预期报错 ->", e)


def demo_build_portfolio_arg():
    banner("示例 2：build_portfolio_arg（构造压测引擎入参）")
    codes, weights = _common.validate_portfolio(["sh.600000", "sh.600004"], [1, 1])
    portfolio = _common.build_portfolio_arg(codes, weights)
    print(json.dumps(portfolio, ensure_ascii=False, indent=2))


def demo_make_response():
    banner("示例 3：make_response（统一响应封装）")
    resp = _common.make_response("demo_tool", {"x": 1, "y": [1, 2, 3]}, warnings=["示例告警"])
    print(json.dumps(json.loads(resp), ensure_ascii=False, indent=2))


def main():
    demo_validate_portfolio()
    demo_build_portfolio_arg()
    demo_make_response()
    print("\n✅ _common 契约层示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
