"""
News Reader MCP 服务客户端测试

需先启动服务：
    python app/services/mcp/server_news_reader.py
默认监听 127.0.0.1:8088（streamable-http）。

测试内容（按流水线顺序，逐步编号打印便于追踪，覆盖全部注册工具）：
    步骤 1  list_tools              列出全部工具并校验核心工具齐全
    步骤 2  list_news_analysts      分析师清单（零 LLM，毫秒级）
    步骤 3  extract_news_meta       结构化提取 NER/标签/事件（真实 LLM）→ 得到 meta
    步骤 4  route_news_analysts     路由决策，推荐分析师（真实 LLM，依赖 meta）
    步骤 5  12 个分析师工具          逐个调用（真实 LLM，依赖 meta）
    步骤 6  finalize_news_analysis  结构化对齐（save=False，不写库）
    步骤 7  search_news_insights    检索历史分析（只读 MongoDB，零 LLM）
    步骤 8  analyze_news            一体式全流程（save=False，最重，约 15~40 秒）

依赖有效 LLM key（NEWS_READER_API_KEY > DASHSCOPE_API_KEY > OPENAI_API_KEY）；
key 缺失/失效或 MongoDB/Redis 未连时，对应步骤会打印工具返回的 error，
属环境性失败而非工具失败，脚本捕获后继续执行后续步骤。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_mcp_news_reader.py
"""
import asyncio
import json
import sys

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

BASE_URL = "http://127.0.0.1:8088/mcp"

# 测试用新闻正文（宏观政策类，便于触发路由到 macro / sentiment 等分析师）
CONTENT = "央行宣布降准 0.5 个百分点，释放长期资金约 1 万亿元，利好银行与地产板块。"

# 必须存在的核心工具（12 个分析师工具由 factory 动态生成，另行按清单校验）
CORE_TOOLS = {
    "extract_news_meta",
    "route_news_analysts",
    "list_news_analysts",
    "finalize_news_analysis",
    "search_news_insights",
    "analyze_news",
}

client = Client(StreamableHttpTransport(BASE_URL))

_STEP = 0


def step(title: str) -> None:
    """打印带序号的步骤标题，便于追踪执行进度。"""
    global _STEP
    _STEP += 1
    print(f"\n{'=' * 70}\n[步骤 {_STEP}] {title}\n{'=' * 70}")


def _text(result) -> str:
    """从 ToolResult 取出文本内容，失败则退回 str(result)。"""
    try:
        return result.content[0].text
    except Exception:
        return str(result)


def _show(result, max_len: int = 800) -> None:
    """截断打印工具返回文本。"""
    text = _text(result)
    print(text if len(text) <= max_len else text[:max_len] + " ...(truncated)")


def _data(result):
    """解析响应 JSON 并返回 data 字段；解析失败返回 None。"""
    try:
        return json.loads(_text(result)).get("data")
    except Exception:
        return None


async def call_tools():
    async with client:
        # ---------------- 步骤 1：列出全部工具 ----------------
        step("list_tools 列出全部工具")
        tools = await client.list_tools()
        names = sorted(t.name for t in tools)
        for n in names:
            print(f"  - {n}")
        missing = CORE_TOOLS - set(names)
        assert not missing, f"缺少核心工具: {missing}"
        print(f"✅ 核心工具齐全，共注册 {len(names)} 个工具")

        # ---------------- 步骤 2：分析师清单（零 LLM） ----------------
        step("list_news_analysts 分析师清单（零 LLM）")
        result = await client.call_tool("list_news_analysts", {})
        _show(result, 600)
        analyst_tools = []
        data = _data(result) or {}
        for a in data.get("analysts", []):
            if a.get("tool_name"):
                analyst_tools.append(a["tool_name"])
        print(f"→ 分析师工具 {len(analyst_tools)} 个: {analyst_tools}")

        # ---------------- 步骤 3：结构化提取（真实 LLM） ----------------
        step("extract_news_meta 结构化提取（真实 LLM）")
        print(f"新闻正文: {CONTENT}")
        result = await client.call_tool("extract_news_meta", {"content": CONTENT})
        _show(result, 600)
        meta_data = _data(result)
        if meta_data is None:
            print("⚠️ 未取到 meta.data（多为 LLM key 缺失/失效）；"
                  "后续依赖 meta 的步骤将以空 meta 尝试，失败属预期")
            meta_payload = ""
        else:
            meta_payload = json.dumps(meta_data, ensure_ascii=False)

        # ---------------- 步骤 4：路由决策（真实 LLM） ----------------
        step("route_news_analysts 路由决策（真实 LLM，依赖 meta）")
        result = await client.call_tool(
            "route_news_analysts", {"content": CONTENT, "meta": meta_payload}
        )
        _show(result, 600)

        # ---------------- 步骤 5：逐个调用 12 个分析师工具 ----------------
        step(f"分析师工具逐个调用（真实 LLM，共 {len(analyst_tools)} 个）")
        collected = {}
        for i, tool_name in enumerate(analyst_tools, 1):
            print(f"\n  [{i}/{len(analyst_tools)}] {tool_name}")
            try:
                result = await client.call_tool(
                    tool_name, {"content": CONTENT, "meta": meta_payload}
                )
                d = _data(result)
                if isinstance(d, dict) and d.get("report"):
                    collected[d.get("agent_name", tool_name)] = d["report"]
                    print(f"     ✅ 报告长度 = {len(d['report'])}")
                    print(d['report'][:1000])
                else:
                    _show(result, 300)
            except Exception as e:
                print(f"     ⚠️ 调用失败: {e}")
        print(f"\n→ 成功产出报告的分析师 {len(collected)} 个: {list(collected.keys())}")

        # ---------------- 步骤 6：结构化对齐（save=False 不写库） ----------------
        step("finalize_news_analysis 结构化对齐（save=False，不写库）")
        analyses = json.dumps(collected, ensure_ascii=False) if collected else "{}"
        result = await client.call_tool(
            "finalize_news_analysis",
            {"content": CONTENT, "meta": meta_payload, "analyses": analyses, "save": False},
        )
        _show(result, 600)

        # ---------------- 步骤 7：检索历史分析（只读 Mongo） ----------------
        step("search_news_insights 检索历史分析（只读 MongoDB，零 LLM）")
        result = await client.call_tool(
            "search_news_insights", {"query": "降准", "limit": 3}
        )
        _show(result, 600)

        # ---------------- 步骤 8：一体式全流程（save=False） ----------------
        step("analyze_news 一体式分析（save=False，约 15~40 秒）")
        result = await client.call_tool("analyze_news", {"content": CONTENT, "save": False})
        _show(result, 800)

    print(f"\n{'=' * 70}\n✅ News Reader MCP 全部工具测试执行完毕\n{'=' * 70}")


if __name__ == "__main__":
    try:
        asyncio.run(call_tools())
    except Exception as e:
        print(
            f"❌ 连接失败（服务是否已启动: "
            f"python app/services/mcp/server_news_reader.py）: {e}"
        )
        sys.exit(1)
