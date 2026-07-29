import asyncio
import sys

sys.path.insert(0, "F:\\project_work\\hf\\AI-Invest")

from fastmcp import Client

# 后端需先启动：python -m app
# 注意：FastMCP Client 对以 /sse 结尾的 URL 使用 SSE 传输，与服务器 mcp.sse_app() 对应。
client = Client("http://localhost:8000/mcp/sse")


async def call_tool():
    async with client:
        # 列出可用工具
        tools = await client.list_tools()
        print("可用工具:")
        for tool in tools:
            print(f"  - {tool.name}")

        # 调用 chat 工具进行简单对话测试
        try:
            result = await client.call_tool("greet", {"name": "你好"})
            print("\nchat 工具返回:")
            print(result)
        except Exception as e:
            print(f"\nchat 工具调用失败: {e}")


if __name__ == "__main__":
    asyncio.run(call_tool())
