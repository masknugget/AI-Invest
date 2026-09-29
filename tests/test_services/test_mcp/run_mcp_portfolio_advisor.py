"""
Portfolio Advisor MCP 服务客户端测试

需先启动服务：
    python app/services/mcp/server_portfolio_advisor.py
默认监听 127.0.0.1:8087（streamable-http）。

测试内容：
1. 列出全部工具（预期 5 个 portfolio_* 工具）
2. 调用 portfolio_rebalance_suggestion（纯本地计算，无网络依赖）
3. 调用 portfolio_diagnosis（依赖行情源：MongoDB / akshare / yfinance，
   本机数据不可用时会打印工具返回的 error，属环境性失败而非工具失败）
4. 调用 portfolio_risk_alerts（行业查询依赖 MongoDB，失败自动归入未知行业）
"""
import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

BASE_URL = "http://127.0.0.1:8087/mcp"

# 调仓测试用真实组合：取预计算分数文件前 4 只
project_root = Path(__file__).resolve().parents[3]
scores_path = (
    project_root / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)

client = Client(StreamableHttpTransport(BASE_URL))


def _load_codes(n: int = 4):
    codes = []
    with open(scores_path, encoding="utf-8") as f:
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
        expected = {
            "portfolio_diagnosis",
            "portfolio_risk_alerts",
            "portfolio_rebalance_suggestion",
            "portfolio_stress_test",
            "portfolio_full_report",
        }
        actual = {t.name for t in tools}
        for t in tools:
            print(f"  - {t.name}")
        missing = expected - actual
        assert not missing, f"缺少工具: {missing}"
        print(f"✅ 5 个 portfolio 工具全部注册 (共 {len(actual)} 个)")

        codes = _load_codes()
        weights = [round(1.0 / len(codes), 4)] * len(codes)
        weights[-1] = round(1.0 - sum(weights[:-1]), 4)
        print(f"\n测试组合: {codes} / {weights}")

        print("\n--- portfolio_rebalance_suggestion ---")
        result = await client.call_tool(
            "portfolio_rebalance_suggestion",
            {"codes": codes, "weights": weights, "max_actions": 1, "top_k": 3},
        )
        _show(result)

        print("\n--- portfolio_diagnosis ---")
        result = await client.call_tool(
            "portfolio_diagnosis", {"codes": codes, "weights": weights}
        )
        _show(result)

        print("\n--- portfolio_risk_alerts ---")
        result = await client.call_tool(
            "portfolio_risk_alerts", {"codes": codes, "weights": weights}
        )
        _show(result)


if __name__ == "__main__":
    try:
        asyncio.run(call_tools())
    except Exception as e:
        print(f"❌ 连接失败（服务是否已启动: python app/services/mcp/server_portfolio_advisor.py）: {e}")
        sys.exit(1)
