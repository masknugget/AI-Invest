"""
portfolio_advice MCP 工具示例总入口 —— 依次以子进程运行本目录全部 run_*.py 示例。

说明：这里是「像 example 那样直接调用并打印」的用法示例，不是断言型单测。
      common 可离线运行；data_source / diagnosis / risk_alerts / stress_test /
      rebalance / full_report 需 MongoDB / 行情数据 / 预计算分数文件可访问。

覆盖模块（app/services/mcp/tools/portfolio_advice）：
    _common.py / data_source.py / diagnosis.py / risk_alerts.py /
    stress_test.py / rebalance.py / full_report.py / prompt_portfilo.py

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_all.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 顺序：common（纯函数）→ data_source / diagnosis / risk_alerts / stress_test / rebalance / full_report
#      → prompt_portfilo（依赖 full_report + rebalance，并会真实调 LLM）
SUITES = [
    "run_common.py",
    "run_data_source.py",
    "run_diagnosis.py",
    "run_risk_alerts.py",
    "run_stress_test.py",
    "run_rebalance.py",
    "run_full_report.py",
    "run_prompt_portfilo.py",
]


def main():
    failed = []
    for name in SUITES:
        print(f"\n{'=' * 60}\n>>> {name}\n{'=' * 60}")
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(HERE / name)],
            cwd=str(HERE.parents[3]),
        )
        if proc.returncode != 0:
            failed.append(name)

    print(f"\n{'=' * 60}")
    if failed:
        print(f"❌ {len(failed)}/{len(SUITES)} 个示例非零退出: {', '.join(failed)}")
        print("   （data_source / diagnosis / full_report 若因 MongoDB 未连、行情缺失而失败，属预期）")
        return False
    print(f"✅ 全部 {len(SUITES)} 个示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
