"""
News Reader 报告 Prompt 构建工具（阶段1/2 真实 LLM，阶段3 仅拼装 Prompt）。

与 pipeline.py / router.py 正交：本模块不调用分析师 LLM，也不生成综合报告，
只负责把「结构化提取 + 路由决策 + 分析师 Prompt」拼装成可直接喂给 LLM 的
「写一篇报告」Prompt 并返回，供上层自行决定何时/由谁执行。

流程：
- 步骤1  extract_news_meta(content)         结构化提取 NER/标签/事件（真实 LLM）
- 步骤2  route_news_analysts(content, meta) 服务端 LLM 路由，得到推荐分析师（真实 LLM）
- 步骤3  取路由前 top_n 个分析师，各自 Prompt 与 content/ner/label/event 拼装成报告 Prompt

两个入口：
- build_report_prompts(content)      每个分析师一份独立报告 Prompt（dict）
- build_merged_report_prompt(content) 多分析师合并为「一篇综合报告」的单一 Prompt
  （共享上下文只出现一次 + 综合指令 + 各分析师框架作为并列「分析视角」）
  纯拼装逻辑见 merge_analyst_prompts(content, meta, agent_names)。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.mcp.tools.news_reader import pipeline, router
from recommender.news_reader.agents.analyst.factory import create_analyst
from recommender.news_reader.consumer.news import build_p_data

# 步骤3 默认取用路由结果中前多少个分析师
DEFAULT_TOP_N = 2


def _unwrap(resp: str, step: str) -> Dict[str, Any]:
    """解析工具响应封装（{"status", "data", "error", ...}），失败时抛异常。"""
    parsed = json.loads(resp)
    if parsed.get("status") != "success":
        raise RuntimeError(f"{step} 失败: {parsed.get('error')}")
    return parsed.get("data") or {}


def _extract_and_route(content: str) -> tuple[Dict[str, Any], List[str]]:
    """步骤1/2（真实 LLM）：结构化提取 + 路由决策，返回 (meta, agent_names)。"""
    print(f"[report_prompt] 步骤1 extract_news_meta: 内容长度={len(content)}")
    meta = _unwrap(pipeline.extract_news_meta(content), "extract_news_meta")
    print(f"[report_prompt] 步骤1 完成: meta keys={list(meta.keys())}")

    print("[report_prompt] 步骤2 route_news_analysts: 路由决策")
    route = _unwrap(
        router.route_news_analysts(content, json.dumps(meta, ensure_ascii=False)),
        "route_news_analysts",
    )
    agent_names: List[str] = route.get("agent_names", [])
    print(f"[report_prompt] 步骤2 完成: 推荐 agents={agent_names}")
    return meta, agent_names


def build_report_prompts(content: str, top_n: int = DEFAULT_TOP_N) -> Dict[str, Any]:
    """端到端构建「写一篇报告」的 Prompt（步骤1/2 走真实 LLM，步骤3 仅拼装）。

    参数
    ----
    content : str
        新闻正文。
    top_n : int
        步骤3 从路由推荐名单中取用的前 N 个分析师，默认 2。

    返回
    ----
    dict：{
        "content":     新闻正文,
        "meta":        步骤1 结构化提取结果 {data_ner, data_label, data_event},
        "agent_names": 步骤2 路由推荐的全部分析师名单,
        "selected":    步骤3 实际取用的前 top_n 个分析师,
        "prompts":     {agent_name: 报告 Prompt 字符串, ...},
    }
    """
    # 步骤1/2：结构化提取 + 路由决策（真实 LLM）
    meta, agent_names = _extract_and_route(content)

    # 步骤3：取前 top_n 个分析师，拼装「写一篇报告」的 Prompt（不调用 LLM）
    selected = agent_names[:top_n]
    p_data = build_p_data(content, meta)
    prompts: Dict[str, str] = {}
    for name in selected:
        p_analyst, specialty = create_analyst(name)
        if not p_analyst:
            print(f"[report_prompt] 步骤3 跳过未知分析师: {name}")
            continue
        # content + ner + label + event + 分析师 Prompt => 写一篇报告的 Prompt
        prompts[name] = p_data + p_analyst
        print(f"[report_prompt] 步骤3 拼装报告 Prompt: {name}（{specialty}）")

    return {
        "content": content,
        "meta": meta,
        "agent_names": agent_names,
        "selected": selected,
        "prompts": prompts,
    }


# 多视角合并为「一篇综合报告」的写作指令：共享上下文只出现一次，
# 各分析师框架作为并列「分析视角」，要求模型综合所有维度只产出一份统一报告。
_MERGED_REPORT_INSTRUCTION = """

# 多视角综合分析报告 Prompt

**角色设定**：你是一位资深财经主笔兼多领域首席分析师，能把宏观、行业、微观、
情绪、估值、风险等多个专业视角整合为一份逻辑连贯、数据驱动的深度报告。

**任务目标**：下方给出同一则新闻的多个「分析视角」，每个视角附带其专属的分析框架
与输出模板。请综合调用全部视角的分析维度，对新闻做一次完整分析，**只输出一份统一的
Markdown 综合报告**，不要按视角分别输出多份报告。

**关键约束**：
1. 各视角自带的「Output Format / 输出格式」模板仅作为**分析维度清单**参考，用于提醒
   不要遗漏该视角的关键分析点；最终报告的整体结构由你统一编排。
2. 报告需体现视角之间的交叉印证与结论收敛（如宏观利好是否被微观基本面、估值与情绪
   资金面共同支持），而非简单罗列各视角结论。
3. 涉及未证实信息标注 [未证实]；区分名义/实际、存量/流量；不得因果谬误或合成谬误。
4. 一轮完成：禁止输出「请提供更多背景」或「下一节再分析」，所有维度在本轮填满。
5. 全文使用 Markdown，层级分明，重点数据与核心逻辑加粗。

**建议报告结构**（可按新闻实际灵活调整）：
- 一、核心结论与投资含义（开门见山）
- 二、新闻事实与预期差
- 三、分视角深度分析（整合下方各分析视角的关键维度）
- 四、交叉印证与主要分歧
- 五、风险提示、关键假设与待验证信号

---

**以下是本则新闻的各分析视角：**

"""


def merge_analyst_prompts(
    content: str,
    meta: Dict[str, Any],
    agent_names: List[str],
) -> str:
    """把多个分析师专长合并为「一篇综合报告」的单一 Prompt（纯拼装，零 LLM）。

    与逐个分析师 Prompt（build_report_prompts 的 prompts）的区别：
    - 共享上下文（content/ner/label/event）只出现一次，避免逐份重复膨胀；
    - 各分析师 Prompt 作为并列「分析视角」章节，由综合指令约束模型只产出一份统一报告。

    参数
    ----
    content : str           新闻正文。
    meta : dict             extract_news_meta 的结构化提取结果（含 data_ner/label/event）。
    agent_names : list[str] 需要纳入综合分析的分析师名单（如路由结果的前 N 个）。

    返回：合并后的单一 Prompt 字符串。
    """
    p_data = build_p_data(content, meta)
    sections: List[str] = []
    for idx, name in enumerate(agent_names, 1):
        p_analyst, specialty = create_analyst(name)
        if not p_analyst:
            print(f"[report_prompt] merge 跳过未知分析师: {name}")
            continue
        sections.append(
            f"## 分析视角{idx}：{specialty}（内部 Agent: {name}）\n{p_analyst}"
        )
        print(f"[report_prompt] merge 纳入分析视角{idx}: {name}（{specialty}）")
    if not sections:
        raise ValueError("agent_names 中没有可识别的分析师，无法合并报告 Prompt")
    return p_data + _MERGED_REPORT_INSTRUCTION + "\n\n".join(sections)


def build_merged_report_prompt(
    content: str, top_n: int = DEFAULT_TOP_N
) -> Dict[str, Any]:
    """端到端构建「一篇综合报告」的单一 Prompt（步骤1/2 真实 LLM，步骤3 仅拼装）。

    与 build_report_prompts 相同的步骤1/2，但步骤3 把前 top_n 个分析师合并为一份 Prompt。

    返回 dict：{
        "content":       新闻正文,
        "meta":          步骤1 结构化提取结果,
        "agent_names":   步骤2 路由推荐的全部分析师,
        "selected":      步骤3 纳入综合的前 top_n 个分析师,
        "merged_prompt": 合并后的单一综合报告 Prompt 字符串,
    }
    """
    meta, agent_names = _extract_and_route(content)
    selected = agent_names[:top_n]
    merged_prompt = merge_analyst_prompts(content, meta, selected)
    print(f"[report_prompt] 合并完成: {len(selected)} 个视角, Prompt 长度={len(merged_prompt)}")
    return {
        "content": content,
        "meta": meta,
        "agent_names": agent_names,
        "selected": selected,
        "merged_prompt": merged_prompt,
    }
