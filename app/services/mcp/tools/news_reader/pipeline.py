"""
News Reader 流水线工具（docs/news_reader_mcp_design.md 第 4 节）。

工具编排约定：
- 每个工具只做三件事：契约校验/解析（contract.py）→ 调用 service 层 → 响应封装
- 服务端不做综合报告/解读文案；综合工作由平台 LLM 基于各 Agent 报告完成
- 流水线阶段：extract_news_meta → 各分析师工具（analysts.py 生成，可并行 ×N）
  → finalize_news_analysis；analyze_news 为无法多轮编排客户端提供的一体式封装
"""

from __future__ import annotations

from typing import Any

from app.services.mcp.tools.news_reader import contract
from app.services.news_analysis import service


async def extract_news_meta(content: str) -> str:
    """
    对新闻做结构化提取：命名实体(ner) + 分类标签(label) + 事件关系(event)。

    服务端对三路提取并行执行（asyncio.gather），单次调用约 2~6 秒，
    提取阶段使用小模型，成本低、速度快；重复新闻命中 Redis 缓存（24h）
    时零 LLM 调用、亚秒返回。

    返回 data：{"data_ner": ..., "data_label": ..., "data_event": ...}。
    下一步：读取 data_label，按各分析师工具 description 中的路由规则
    选定分析师并并行调用（并发 ≤3）。
    """
    tool = "extract_news_meta"
    try:
        content = contract.validate_content(content)
        meta = await service.extract_meta(content)
        return contract.make_response(tool, meta)
    except ValueError as e:
        return contract.error_response(tool, str(e))
    except Exception as e:
        return contract.error_response(tool, f"结构化提取失败: {e}")


async def analyst_response(
    content: Any,
    meta: Any,
    agent_name: str,
    tool_name: str,
) -> str:
    """单个分析师工具的共享实现（由 analysts.py 按 Agent 生成独立工具）。

    agent_name 固定于工具本身（如 macro_analyst 固定为 MacroAgent），
    tool_name 用于错误响应的 tool 字段标识。
    """
    try:
        content = contract.validate_content(content)
        meta_dict = contract.parse_meta(meta)
        report = await service.run_analyst(content, meta_dict, agent_name)
        return contract.make_response(
            tool_name, {"agent_name": agent_name, "report": report}
        )
    except ValueError as e:
        return contract.error_response(tool_name, str(e))
    except Exception as e:
        return contract.error_response(tool_name, f"分析 Agent 运行失败: {e}")


async def finalize_news_analysis(
    content: str,
    meta: str,
    analyses: str,
    save: bool = True,
) -> str:
    """
    将多 Agent 分析结果结构化为标准资讯 JSON（align_data schema），并可选入库。

    返回 data：{"data_align": {title, sub_title, summary, content(md), stock_codes[],
    category, tags, keywords, metadata{impact_level, sentiment, urgency,
    routing_agents, ...}, article_id, create_time}, "saved": bool}。
    save=True（默认）时写入 MongoDB insight_agg 集合。

    注意：综合解读文案请由你（平台 LLM）基于各分析师报告自行撰写；
    本工具只做结构化对齐与入库，不生成报告。若需入库你的解读，
    可先将其并入 analyses（如 {"综合解读": "..."}）再调用本工具。

    参数
    ----
    content : str
        新闻正文。
    meta : str
        extract_news_meta 返回 JSON 的 data 字段，原样回传；
        误传完整响应封装也能自动兼容。
    analyses : str
        JSON 对象，形如 {"MicroAgent": "<markdown 报告>", "SentimentAgent": "..."}；
        只跑了一个分析师时可直接回传其响应（{"agent_name", "report"} 形态），
        允许附加你自己撰写的综合解读（值为字符串即可）。
    save : bool
        是否写入 MongoDB insight_agg，默认 True。
    """
    tool = "finalize_news_analysis"
    try:
        content = contract.validate_content(content)
        meta_dict = contract.parse_meta(meta)
        analyses_dict = contract.parse_analyses(analyses)
        data_align = await service.finalize(
            content, meta_dict, analyses_dict, save=save
        )
        return contract.make_response(
            tool, {"data_align": data_align, "saved": save}
        )
    except ValueError as e:
        return contract.error_response(tool, str(e))
    except Exception as e:
        return contract.error_response(tool, f"结构化对齐失败: {e}")


async def analyze_news(content: str, save: bool = True) -> str:
    """
    一体式新闻分析（提取 → 路由 → 全部 Agent → 结构化对齐），约 15~40 秒。

    仅供无法多轮编排的客户端使用；支持并行/按需的客户端请优先使用拆分工具
    （extract_news_meta → 并行调用各分析师工具 → 你自行综合），
    拆分路径服务端 LLM 调用更少、耗时更低（8~12 秒），且综合质量由你掌控。
    重复新闻命中 Redis 缓存（24h）时亚秒返回。

    save=True（默认）时 data_align 写入 MongoDB insight_agg。
    返回 data：完整流水线结果（含各 Agent 报告与 data_align）。
    """
    tool = "analyze_news"
    try:
        content = contract.validate_content(content)
        out_data = await service.analyze_news(content, save=save)
        return contract.make_response(tool, out_data)
    except ValueError as e:
        return contract.error_response(tool, str(e))
    except Exception as e:
        return contract.error_response(tool, f"新闻分析失败: {e}")
