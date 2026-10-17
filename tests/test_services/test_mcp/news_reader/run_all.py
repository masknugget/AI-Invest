"""
News Reader MCP 工具示例总入口 —— 依次以子进程运行本目录全部 run_*.py 示例。

说明：这里是「像 example 那样直接调用并打印」的用法示例，不是断言型单测。
      contract / insights 可离线运行；pipeline / analysts 需有效 LLM key，
      insights 的检索部分需 MongoDB 可连接。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_all.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 顺序：contract（纯函数）→ insights（只读）→ pipeline / analysts（真实 LLM）
SUITES = [
    "run_contract.py",
    "run_insights.py",
    "run_pipeline.py",
    "run_analysts.py",
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
        print("   （pipeline / analysts 若因 LLM key 失效、insights 若因 Mongo 未连而失败，属预期）")
        return False
    print(f"✅ 全部 {len(SUITES)} 个示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
