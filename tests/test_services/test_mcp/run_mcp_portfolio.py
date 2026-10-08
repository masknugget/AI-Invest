"""
Portfolio Advisor MCP 客户端调用示例（非测试代码）

需先启动服务：
    python -m app.services.mcp.server_portfolio_advisor
默认 streamable-http，监听 0.0.0.0:8087。

用法：
    python tests/test_services/test_mcp/run_mcp_portfolio.py
"""
import asyncio
import json
import sys
from pathlib import Path

# Windows 控制台 GBK 无法输出 emoji，统一改为 UTF-8（与 app/__main__.py 一致）
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

BASE_URL = "http://127.0.0.1:8087/mcp"

client = Client(StreamableHttpTransport(BASE_URL))

# 示例组合（baostock 风格代码，weights 总和不为 1 时服务端自动归一化）
# 注意：diagnosis / stress_test / full_report 需要行情源（MongoDB / akshare），
# 本机数据不可用时工具会返回 error，属环境性失败而非工具失败。
CODES = ["sz.300005", "sz.300291", "sh.601689", "sz.300237", "sz.300121"]
WEIGHTS = [0.2, 0.2, 0.2, 0.2, 0.2]

# 调仓建议要求组合内股票在预计算得分文件中，取文件前 4 只
_scores_path = (
    Path(__file__).resolve().parents[3]
    / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)


def _load_rebalance_codes(n: int = 4):
    codes = []
    with open(_scores_path, encoding="utf-8") as f:
        for line in f:
            codes.append(json.loads(line)["code"])
            if len(codes) >= n:
                break
    return codes


def _show(result, max_len: int = 800):
    try:
        text = result.content[0].text
    except Exception:
        text = str(result)
    text = text if len(text) <= max_len else text[:max_len] + " ...(truncated)"
    print(text)


async def call_tools():
    async with client:
        tools = await client.list_tools()
        print("可用工具:")
        for tool in tools:
            print(f"  - {tool.name}")

        print("\n--- portfolio_diagnosis ---")
        _show(await client.call_tool(
            "portfolio_diagnosis", {"codes": CODES, "weights": WEIGHTS}
        ))

        print("\n--- portfolio_risk_alerts ---")
        _show(await client.call_tool(
            "portfolio_risk_alerts", {"codes": CODES, "weights": WEIGHTS}
        ))

        print("\n--- portfolio_stress_test (history) ---")
        _show(await client.call_tool(
            "portfolio_stress_test",
            {"codes": CODES, "weights": WEIGHTS, "scenario_type": "history"},
        ))

        print("\n--- portfolio_rebalance_suggestion ---")
        rb_codes = _load_rebalance_codes()
        rb_weights = [round(1.0 / len(rb_codes), 4)] * len(rb_codes)
        rb_weights[-1] = round(1.0 - sum(rb_weights[:-1]), 4)
        _show(await client.call_tool(
            "portfolio_rebalance_suggestion",
            {"codes": rb_codes, "weights": rb_weights, "max_actions": 1, "top_k": 3},
        ))

        print("\n--- portfolio_full_report ---")
        _show(await client.call_tool(
            "portfolio_full_report", {"codes": CODES, "weights": WEIGHTS}
        ))


if __name__ == "__main__":
    try:
        asyncio.run(call_tools())
    except Exception as e:
        print(f"❌ 连接失败（服务是否已启动: python -m app.services.mcp.server_portfolio_advisor）: {e}")
        sys.exit(1)
