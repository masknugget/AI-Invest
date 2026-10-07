"""
News Reader MCP 工具契约层。

职责边界：本模块是 MCP 协议边界内的全部横切关注点，工具函数只负责
「校验/解析 → 调用服务层 → 封装响应」的编排。

包含：
- 统一响应封装（status / tool / data / warnings / error），与 portfolio_advice 工具一致
- 平台 LLM 回传参数的宽容解析：
    parse_meta()     接受 extract_news_meta 返回的 data 字段（裸 meta dict）或
                     完整工具响应封装（{"status": ..., "data": {...}}），
                     统一返回 {data_ner, data_label, data_event}
    parse_analyses() 接受 {agent_name: markdown} JSON，同样可容忍响应封装包裹
- 参数校验：正文、agent_name（名单来自 factory.list_agent_names()，单一事实来源，
  不再硬编码）、limit
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# meta 的固定结构键（aextract_meta 的返回契约）
META_REQUIRED_KEYS = ("data_ner", "data_label", "data_event")

LIMIT_MIN = 1
LIMIT_MAX = 100
LIMIT_DEFAULT = 10

# 类型别名：流水线阶段间传递的结构化对象
NewsMeta = Dict[str, Any]
AgentAnalyses = Dict[str, str]


# ----------------------------------------------------------------------------
# 响应封装
# ----------------------------------------------------------------------------

def make_response(
    tool: str,
    data: Any = None,
    status: str = "success",
    warnings: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> str:
    """构造统一 JSON 字符串响应（MCP 工具返回 str，与 portfolio_advice 一致）。"""
    payload = {
        "status": status,
        "tool": tool,
        "data": data,
        "warnings": warnings or [],
        "error": error,
    }
    return json.dumps(_to_jsonable(payload), ensure_ascii=False)


def error_response(tool: str, message: str) -> str:
    return make_response(tool, status="error", error=message)


def _to_jsonable(obj: Any) -> Any:
    """将 datetime / date 等非 JSON 原生类型转为可序列化类型。"""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if obj == obj and abs(obj) != float("inf") else str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    return str(obj)


# ----------------------------------------------------------------------------
# 平台回传参数解析（宽容模式：可接受裸数据或完整工具响应封装）
# ----------------------------------------------------------------------------

def _unwrap_envelope(raw: Any, arg_name: str) -> Any:
    """若 raw 是本工具集的响应封装（含 status+data 键），剥出 data 字段。

    平台 LLM 常把上一步工具的完整返回原样回传，此处自动容错。
    """
    if isinstance(raw, dict) and "status" in raw and "data" in raw:
        return raw["data"]
    return raw


def parse_meta(raw: Any) -> NewsMeta:
    """解析 meta 参数为结构化的提取结果 dict。

    接受：JSON 字符串 / 已解析 dict / 完整工具响应封装。
    返回 dict 至少含 data_ner / data_label / data_event 三键（允许附加键）。
    """
    meta = _loads_if_str(raw, "meta")
    meta = _unwrap_envelope(meta, "meta")
    if not isinstance(meta, dict):
        raise ValueError("meta 应为 JSON 对象（extract_news_meta 返回的 data 字段）")
    missing = [k for k in META_REQUIRED_KEYS if k not in meta]
    if missing:
        raise ValueError(
            f"meta 缺少字段 {missing}：请将 extract_news_meta 返回的 data 字段"
            "原样回传，不要只传其中一部分"
        )
    return meta


def parse_analyses(raw: Any) -> AgentAnalyses:
    """解析 analyses 参数为 {agent_name: markdown 报告}。

    接受：JSON 字符串 / 已解析 dict / 完整工具响应封装；
    单个 run_news_analyst 响应形态（{"agent_name", "report"}）自动归一。
    允许平台 LLM 附加自己撰写的综合解读（任意键，值为字符串即可）。
    """
    analyses = _loads_if_str(raw, "analyses")
    analyses = _unwrap_envelope(analyses, "analyses")
    if (
        isinstance(analyses, dict)
        and "agent_name" in analyses
        and "report" in analyses
        and len(analyses) <= 3
    ):
        # run_news_analyst 的 data 形态：{"agent_name": ..., "report": ...}
        analyses = {analyses["agent_name"]: analyses["report"]}
    if not isinstance(analyses, dict) or not analyses:
        raise ValueError(
            "analyses 应为非空 JSON 对象，形如 "
            '{"MicroAgent": "<markdown 报告>", "SentimentAgent": "..."}'
        )
    bad = [k for k, v in analyses.items() if not isinstance(v, str)]
    if bad:
        raise ValueError(f"analyses 中以下 Agent 的值不是字符串: {bad}")
    return analyses


def _loads_if_str(raw: Any, arg_name: str) -> Any:
    if isinstance(raw, str):
        if not raw.strip():
            raise ValueError(f"{arg_name} 不能为空（应为 JSON 字符串）")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{arg_name} 不是合法 JSON: {e}；请将上一步工具返回的 data 字段原样回传"
            ) from e
    return raw


# ----------------------------------------------------------------------------
# 参数校验
# ----------------------------------------------------------------------------

def validate_content(content: Any) -> str:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("新闻内容 content 不能为空")
    return content


def list_valid_agents() -> List[str]:
    """可用分析 Agent 名单（来自 factory，单一事实来源）。"""
    from recommender.news_reader.agents.analyst.factory import list_agent_names

    return list_agent_names()


def validate_agent_name(agent_name: Any) -> str:
    if not isinstance(agent_name, str) or not agent_name:
        raise ValueError("agent_name 不能为空")
    valid = list_valid_agents()
    if agent_name not in valid:
        raise ValueError(
            f"未知 agent_name: {agent_name}，可选：{' / '.join(valid)}"
        )
    return agent_name


def validate_limit(limit: Any) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError(f"limit 须为整数，默认 {LIMIT_DEFAULT}")
    if not (LIMIT_MIN <= limit <= LIMIT_MAX):
        raise ValueError(f"limit 须在 {LIMIT_MIN}~{LIMIT_MAX} 之间")
    return limit
