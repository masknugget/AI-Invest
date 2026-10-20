"""
risk_alerts.py 风险指标用法示例（真实数据源，零 LLM）。

演示 portfolio_risk_alerts：返回行业分布、行业 HHI、规则化风险条目与告警清单。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_risk_alerts.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import risk_alerts


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_risk_alerts():
    banner("示例：portfolio_risk_alerts（三只标的行业分布 + 风险指标）")
    try:
        resp = json.loads(
            risk_alerts.portfolio_risk_alerts(
                ["sh.600000", "sh.600004", "sh.600519"], [0.4, 0.3, 0.3]
            )
        )
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print("portfolio_risk_alerts 失败 ->", e)


def main():
    demo_risk_alerts()
    print("\n✅ risk_alerts 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
