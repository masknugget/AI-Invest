"""
stress_test.py 压力测试用法示例（真实计算引擎，零 LLM）。

演示 portfolio_stress_test 三类情景：
    scenario   宏观情景（不依赖行情）
    sector     行业冲击（不依赖行情）
    history    历史事件重演（依赖行情；本地已入库代码可算）

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_stress_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import stress_test

CODES = ["sz.000001", "sz.000002"]
WEIGHTS = [0.5, 0.5]


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_scenario(stype: str) -> None:
    banner(f"示例：portfolio_stress_test(scenario_type={stype!r})")
    try:
        resp = json.loads(
            stress_test.portfolio_stress_test(CODES, WEIGHTS, scenario_type=stype)
        )
        results = (resp.get("data") or {}).get("results", [])
        print(f"status   -> {resp['status']}")
        print(f"warnings -> {resp.get('warnings')}")
        print(f"results  -> {len(results)} 条")
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:1200])
    except Exception as e:
        print(f"stress_test({stype}) 失败 -> {e}")


def main():
    for stype in ("scenario", "sector", "history"):
        demo_scenario(stype)
    print("\n✅ stress_test 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
