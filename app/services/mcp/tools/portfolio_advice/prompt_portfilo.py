"""
prompt_portfilo.py —— 将 portfolio_advice 工具的 JSON 输出包装为 HTML 报告生成 prompt。

本模块面向"生成可视化 HTML 报告"的场景：portfolio_advice 下的 MCP 工具
（full_report / rebalance / stress_test 等）都只返回结构化 JSON，
无法直接用于渲染报告。此处的函数把这些 JSON 结果格式化为可读文本，
并拼装成一段完整的 prompt 字符串，交给上层 LLM 生成单文件 HTML 报告。

主要函数：
    build_portfolio_html_report_prompt(
        codes, weights, include_rebalance=True, rebalance_objective="composite_score"
    )
        内部调用 portfolio_full_report / portfolio_rebalance_suggestion，
        返回一段完整的 prompt 字符串，供 LLM 生成可视化 HTML 组合分析报告。

设计原则：
    - 所有数值均来自工具真实返回，prompt 中明确要求 LLM 不得虚构数字。
    - 工具调用失败时优雅降级（对应章节显示"暂无数据"），不抛异常中断整体流程。
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional


# ============================================================================
# 维度中文名与指标说明（各数据段构建器共用）
# ============================================================================
_DIM_CN = {
    "drawdown_control":          ("抗回撤能力", "最大回撤（MDD）"),
    "portfolio_diversification": ("资产分散度", "有效标的数 / 风险有效标的数"),
    "position_efficiency":       ("持仓性价比", "夏普比率（Sharpe Ratio）"),
    "return_stability":          ("收益稳定性", "年化波动率"),
    "style_balance":             ("风格均衡",   "风格 HHI / 有效风格数"),
}


# ============================================================================
# 私有辅助
# ============================================================================
def _fmt_pct(v: Any, digits: int = 1) -> str:
    """百分比格式化，None 或异常值返回 'N/A'。"""
    try:
        if v is None:
            return "N/A"
        return f"{float(v):.{digits}f}%"
    except (ValueError, TypeError):
        return "N/A"


def _fmt_num(v: Any, digits: int = 2) -> str:
    """浮点格式化，None 或异常值返回 'N/A'。"""
    try:
        if v is None:
            return "N/A"
        return f"{float(v):.{digits}f}"
    except (ValueError, TypeError):
        return "N/A"


def _parse(json_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """安全解析 JSON，失败或 status=error 时返回 None。"""
    if not json_str:
        return None
    try:
        obj = json.loads(json_str)
        if not isinstance(obj, dict) or obj.get("status") == "error":
            return None
        return obj
    except Exception:
        return None


# ============================================================================
# 数据段构建器
# ============================================================================
def _build_dimensions_section(data: Dict[str, Any]) -> str:
    """将五维评分 JSON 数据格式化为可读文本段。"""
    dims = data.get("dimensions", {})
    composite = dims.get("composite_score")
    geo_composite = dims.get("geometric_composite_score")

    lines = [
        "## 一、组合五维评分",
        "",
        f"- **综合健康分（算术加权）**：{_fmt_num(composite)} / 100",
        f"- **综合健康分（几何加权）**：{_fmt_num(geo_composite)} / 100",
        "",
        "| 维度 | 得分 | 关键指标 |",
        "|------|------|----------|",
    ]

    for key, (cn_name, _metric_desc) in _DIM_CN.items():
        dim = dims.get(key, {})
        score = dim.get("score")
        if key == "drawdown_control":
            mdd = dim.get("max_drawdown")
            metric = f"MDD = {_fmt_pct(mdd * 100, 2) if mdd is not None else 'N/A'}"
        elif key == "portfolio_diversification":
            metric = (
                f"ENB(权重) = {_fmt_num(dim.get('enb_weight_based'))}，"
                f"ENB(风险) = {_fmt_num(dim.get('enb_risk_based'))}"
            )
        elif key == "position_efficiency":
            metric = f"Sharpe = {_fmt_num(dim.get('sharpe_ratio'))}"
        elif key == "return_stability":
            vol = dim.get("annualized_volatility")
            metric = (
                f"年化波动率 = {_fmt_pct(vol * 100, 2) if vol is not None else 'N/A'}"
            )
        else:
            metric = (
                f"风格HHI = {_fmt_num(dim.get('style_hhi'))}，"
                f"有效风格数 = {_fmt_num(dim.get('effective_style_num'), 1)}"
            )
        lines.append(f"| {cn_name} | {_fmt_num(score)} | {metric} |")

    weights = dims.get("dimension_weights", {})
    if weights:
        lines += [
            "",
            "**维度权重**：" + "，".join(
                f"{_DIM_CN.get(k, (k,))[0]}={v}" for k, v in weights.items()
            ),
        ]

    return "\n".join(lines)


def _build_risk_section(data: Dict[str, Any]) -> str:
    """将风险指标 JSON 数据格式化为可读文本段。"""
    risk = data.get("risk", {})
    industry_dist: Dict[str, Any] = risk.get("industry_distribution", {})
    hhi = risk.get("industry_hhi")
    risk_items: List[Dict] = risk.get("risk_items", [])

    lines = [
        "",
        "## 二、行业分布与风险指标",
        "",
        f"- **行业 HHI（赫芬达尔指数）**：{_fmt_num(hhi, 4)}",
        "",
        "**行业分布**：",
    ]
    if industry_dist:
        lines += ["", "| 行业 | 权重占比 |", "|------|----------|"]
        for ind, w in sorted(industry_dist.items(), key=lambda x: -float(x[1])):
            lines.append(f"| {ind} | {_fmt_pct(float(w) * 100)} |")
    else:
        lines.append("暂无行业分布数据。")

    if risk_items:
        lines += ["", "**风险项**："]
        for item in risk_items:
            lines.append(f"- [{item.get('summary', '')}] {item.get('detail', '')}")

    return "\n".join(lines)


def _build_stress_section(stress: Dict[str, Any]) -> str:
    """将压力测试 JSON 数据格式化为可读文本段。"""
    lines = ["", "## 三、压力测试结果", ""]

    # --- 3.1 历史极端行情 ---
    history: List[Dict] = stress.get("history", [])
    lines.append("### 3.1 历史极端行情")
    if history:
        lines += [
            "",
            "| 场景 | 组合损失 | 基准回撤 | 数据覆盖率 |",
            "|------|----------|----------|------------|",
        ]
        for r in history:
            benchmark = r.get("benchmark_drawdown")
            benchmark_pct = (benchmark * 100) if benchmark is not None else None
            coverage = r.get("data_coverage")
            lines.append(
                f"| {r.get('scenario_name', 'N/A')} "
                f"| {_fmt_pct(r.get('portfolio_loss_pct'))} "
                f"| {_fmt_pct(benchmark_pct)} "
                f"| {_fmt_num(coverage, 2) if coverage is not None else 'N/A'} |"
            )
    else:
        lines.append("暂无历史场景数据（可能行情数据不足）。")

    # --- 3.2 宏观情景冲击 ---
    scenario: List[Dict] = stress.get("scenario", [])
    lines += ["", "### 3.2 宏观情景冲击"]
    if scenario:
        lines += [
            "",
            "| 情景 | 组合损失 | 受影响标的数 |",
            "|------|----------|--------------|",
        ]
        for r in scenario:
            lines.append(
                f"| {r.get('scenario_name', 'N/A')} "
                f"| {_fmt_pct(r.get('portfolio_loss_pct'), 2)} "
                f"| {len(r.get('affected_stocks', []))} |"
            )
    else:
        lines.append("暂无宏观情景数据。")

    # --- 3.3 行业板块回调 ---
    sector: List[Dict] = stress.get("sector", [])
    lines += ["", "### 3.3 行业板块回调"]
    if sector:
        lines += [
            "",
            "| 板块 | 回调幅度 | 组合损失 |",
            "|------|----------|----------|",
        ]
        for r in sector:
            callback = r.get("sector_callback_pct")
            callback_pct = (callback * 100) if callback is not None else None
            lines.append(
                f"| {r.get('sector', r.get('scenario_name', 'N/A'))} "
                f"| {_fmt_pct(callback_pct, 0) if callback_pct is not None else 'N/A'} "
                f"| {_fmt_pct(r.get('portfolio_loss_pct'), 2)} |"
            )
    else:
        lines.append("暂无行业板块回调数据。")

    return "\n".join(lines)


def _build_rebalance_section(data: Dict[str, Any]) -> str:
    """将调仓建议 JSON 数据格式化为可读文本段。"""
    plans: List[Dict] = data.get("plans", [])
    objective = data.get("objective", "composite_score")

    if not plans:
        return "\n".join([
            "",
            "## 四、调仓建议",
            "",
            f"优化目标：`{objective}`，暂无可行调仓方案。",
        ])

    lines = [
        "",
        "## 四、调仓建议",
        "",
        f"**优化目标**：`{objective}`，共 {len(plans)} 套方案",
        "",
    ]

    for i, plan in enumerate(plans, 1):
        score_before = plan.get("score_before")
        score_after = plan.get("score_after")
        improvement = plan.get("improvement")
        actions: List[Dict] = plan.get("actions", [])

        lines += [
            f"### 方案 {i}",
            "",
            "| 指标 | 调仓前 | 调仓后 | 变化 |",
            "|------|--------|--------|------|",
            f"| 综合得分 | {_fmt_num(score_before)} | {_fmt_num(score_after)} | {_fmt_num(improvement)} |",
            "",
            "**调仓动作**：",
            "",
            "| 操作 | 调出 | 调入 | 调出权重 | 调入权重 | 理由 |",
            "|------|------|------|----------|----------|------|",
        ]
        for act in actions:
            action_cn = {"replace": "替换", "add": "新增", "remove": "减仓"}.get(
                act.get("action_type", ""), act.get("action_type", "")
            )
            lines.append(
                f"| {action_cn} "
                f"| {act.get('code_out') or '—'} "
                f"| {act.get('code_in') or '—'} "
                f"| {_fmt_pct((act.get('weight_out') or 0) * 100)} "
                f"| {_fmt_pct((act.get('weight_in') or 0) * 100)} "
                f"| {act.get('reason') or '—'} |"
            )

        dims_before: Dict = plan.get("dimensions_before", {})
        dims_after: Dict = plan.get("dimensions_after", {})
        if dims_before and dims_after:
            lines += [
                "",
                "**各维度得分对比**：",
                "",
                "| 维度 | 调仓前 | 调仓后 |",
                "|------|--------|--------|",
            ]
            for dim_key, (cn_name, _) in _DIM_CN.items():
                lines.append(
                    f"| {cn_name} "
                    f"| {_fmt_num(dims_before.get(dim_key))} "
                    f"| {_fmt_num(dims_after.get(dim_key))} |"
                )
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# 主函数
# ============================================================================
def build_portfolio_html_report_prompt(
    codes: List[str],
    weights: List[float],
    include_rebalance: bool = True,
    rebalance_objective: str = "composite_score",
) -> str:
    """
    调用 portfolio_full_report（及可选的 portfolio_rebalance_suggestion），
    将结构化 JSON 结果转换为 HTML 可视化报告生成 prompt。

    参数
    ----
    codes : List[str]
        股票代码列表，baostock 风格（sh.600000 / sz.000001 / hk.00700）。
    weights : List[float]
        各标的权重，长度须与 codes 一致；总和不为 1 时内部自动归一化。
    include_rebalance : bool
        是否同时调用 portfolio_rebalance_suggestion，默认 True。
    rebalance_objective : str
        调仓优化目标，仅在 include_rebalance=True 时生效，默认 "composite_score"。

    返回
    ----
    str
        完整的 prompt 字符串，可直接传入 LLM 生成可视化 HTML 报告。

    示例
    ----
    >>> prompt = build_portfolio_html_report_prompt(
    ...     codes=["sz.000001", "sz.000002"],
    ...     weights=[0.5, 0.5],
    ... )
    >>> # 将 prompt 发送给 LLM，获取 HTML 字符串
    """
    from app.services.mcp.tools.portfolio_advice import _common
    from app.services.mcp.tools.portfolio_advice.full_report import portfolio_full_report
    from app.services.mcp.tools.portfolio_advice.rebalance import (
        portfolio_rebalance_suggestion,
    )

    codes, weights = _common.validate_portfolio(codes, weights)

    # --- 调用工具，获取原始 JSON ---
    full_report_raw = portfolio_full_report(codes, weights)

    rebalance_raw: Optional[str] = None
    if include_rebalance:
        try:
            rebalance_raw = portfolio_rebalance_suggestion(
                codes, weights, objective=rebalance_objective
            )
        except Exception:
            pass

    # --- 解析并格式化各数据段 ---
    sections: List[str] = []

    fr = _parse(full_report_raw)
    if fr is not None:
        fr_data: Dict = fr.get("data", {})
        sections.append(_build_dimensions_section(fr_data))
        sections.append(_build_risk_section(fr_data))
        sections.append(_build_stress_section(fr_data.get("stress", {})))
    else:
        sections.append(
            "## 组合全景数据\n\n"
            "全景报告数据获取失败，无法展示五维评分、风险指标与压力测试结果。"
        )

    if rebalance_raw is not None:
        rb = _parse(rebalance_raw)
        if rb is not None:
            sections.append(_build_rebalance_section(rb.get("data", {})))

    data_body = "\n".join(sections)

    # --- 持仓摘要行 ---
    today = date.today().isoformat()
    holdings_line = "、".join(f"{c}({w:.1%})" for c, w in zip(codes, weights))

    # --- 拼装完整 prompt ---
    prompt = f"""\
# 角色

你是一名专业的金融数据可视化工程师，精通将结构化投资分析数据转化为清晰、专业、美观的 HTML 报告页面。

# 任务

根据以下投资组合分析数据，生成一个完整的**单文件 HTML 可视化报告**（所有 CSS / JS 内联，不依赖外部资源）。

报告基准日期：{today}
持仓组合：{holdings_line}

---

# 分析数据

{data_body}

---

# HTML 报告生成要求

## 页面结构

1. **报告头部**：大标题"投资组合分析报告"，副标题显示报告日期与持仓组合摘要。
2. **综合健康分**：突出展示综合得分（大字号），用颜色区分评级（≥75 绿色 / ≥50 橙色 / <50 红色）。
3. **五维雷达图**：用 Chart.js（CDN：https://cdn.jsdelivr.net/npm/chart.js）绘制五维得分雷达图；若无法引入 CDN，用纯 CSS/SVG 替代。
4. **五维评分明细**：表格展示各维度得分与关键指标，得分用进度条或色块直观呈现。
5. **行业分布**：饼图或水平条形图展示行业权重占比；旁列行业 HHI 数值与含义说明。
6. **风险提示**：卡片式布局，按严重程度着色（高风险红色 / 中风险橙色 / 低风险绿色）。
7. **压力测试**：三类场景（历史 / 宏观 / 行业）分 Tab 或分组展示，损失幅度用红绿色条形图直观对比。
8. **调仓建议**（若有数据）：每套方案一张卡片，含调仓前后得分对比、具体操作列表；若无方案则省略此节。
9. **页脚免责声明**：固定文案"本报告由规则计算生成，仅供参考，不构成投资建议。市场有风险，投资需谨慎。"

## 视觉规范

- 整体风格：现代金融仪表盘，简洁专业，适当留白。
- 配色：以蓝色系为主调，风险 / 损失用红色，收益 / 优势用绿色，中性用灰色。
- 字体：优先使用系统字体栈（-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif）。
- 响应式：页面最大宽度 1200px，居中显示，移动端可正常阅读。
- 数值精度：百分比保留 1 位小数，得分保留 1 位小数，HHI 保留 4 位小数。

## 数据处理原则

- 所有数值必须来自上方提供的数据，**不得虚构或假设任何数字**。
- 若某节数据缺失或获取失败，对应区域显示"暂无数据"并保留页面结构完整性。
- 压力测试损失值为负数时，展示时取绝对值并标注"↓"或"-"前缀，颜色为红色。

## 输出格式

**只输出完整 HTML 代码**，不要包含任何解释性文字、Markdown 标记或代码块围栏。
HTML 必须是一个完整文档（含 <!DOCTYPE html>、<html>、<head>、<body>），可直接保存为 .html 文件在浏览器中打开。
"""
    return prompt


def portfolio_html_report_prompt(
    codes: List[str],
    weights: List[float],
    include_rebalance: bool = True,
    rebalance_objective: str = "composite_score",
) -> str:
    """
    生成「投资组合可视化 HTML 报告」的完整 prompt 字符串（纯计算，零 LLM 调用）。

    内部先调用 portfolio_full_report（及可选 portfolio_rebalance_suggestion）拿到结构化
    JSON，再把五维评分 / 行业分布与风险 / 三类压力测试 / 调仓建议各数据段格式化为
    Markdown 表格，拼装成一段可直接交给调用方 AI 生成单文件 HTML 报告的完整 prompt。

    本工具自身不做任何 LLM 调用，只返回 prompt 文本；最终 HTML 由调用方 AI 依据该
    prompt 自行生成。

    参数
    ----
    codes : List[str]
        股票代码列表，支持 baostock 风格（sh.600000 / sz.000001 / hk.00700）。
    weights : List[float]
        各标的权重，长度须与 codes 一致；允许总和不为 1，内部自动归一化。
    include_rebalance : bool
        是否同时纳入调仓建议章节，默认 True。
    rebalance_objective : str
        调仓优化目标，仅在 include_rebalance=True 时生效，默认 "composite_score"。

    返回
    ----
    str
        JSON 字符串，结构：{status, tool, data, warnings, error}。
        data.prompt 为完整 prompt 字符串；data.codes / data.weights 为归一化后的持仓；
        data.include_rebalance / data.rebalance_objective 回显本次参数。
    """
    from app.services.mcp.tools.portfolio_advice import _common

    tool = "portfolio_html_report_prompt"
    try:
        clean_codes, clean_weights = _common.validate_portfolio(codes, weights)
        prompt = build_portfolio_html_report_prompt(
            codes=clean_codes,
            weights=clean_weights,
            include_rebalance=include_rebalance,
            rebalance_objective=rebalance_objective,
        )
        data = {
            "prompt": prompt,
            "codes": clean_codes,
            "weights": clean_weights,
            "include_rebalance": include_rebalance,
            "rebalance_objective": rebalance_objective,
        }
        return _common.make_response(tool, data, status="success")
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"HTML 报告 prompt 生成失败: {e}")


__all__ = [
    "build_portfolio_html_report_prompt",
    "portfolio_html_report_prompt",
]
