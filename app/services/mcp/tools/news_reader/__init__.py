"""
News Reader MCP 工具包。

分层：
- contract.py   MCP 边界契约：响应封装 + 平台回传参数宽容解析 + 参数校验
                （Agent 名单来自 factory.list_agent_names()，单一事实来源）
- pipeline.py   流水线工具（docs/news_reader_mcp_design.md 第 4 节）：
                extract_news_meta → finalize_news_analysis + analyze_news 一体式封装
- analysts.py   分析师工具工厂：按 factory 生成 12 个独立分析师 MCP 工具
                （macro_analyst / micro_analyst / ...，单一事实来源）
- insights.py   存储与发现查询工具：search_news_insights（只读 MongoDB，零 LLM）、
                list_news_analysts（分析师清单，零 LLM）

设计原则：服务端做结构化提取与确定性流水线；路由决策、并行发起与综合
解读由平台 LLM 完成。
"""

from app.services.mcp.tools.news_reader.analysts import (
    agent_tool_name,
    build_analyst_tools,
)
from app.services.mcp.tools.news_reader.insights import (
    list_news_analysts,
    search_news_insights,
)
from app.services.mcp.tools.news_reader.pipeline import (
    analyze_news,
    extract_news_meta,
    finalize_news_analysis,
)

__all__ = [
    "extract_news_meta",
    "build_analyst_tools",
    "agent_tool_name",
    "finalize_news_analysis",
    "search_news_insights",
    "list_news_analysts",
    "analyze_news",
]
