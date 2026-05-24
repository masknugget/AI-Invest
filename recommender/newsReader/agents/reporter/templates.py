"""
报告模板系统

提供多种财经新闻写作模板：
- flash: 快讯模板
- news: 标准新闻模板  
- analysis: 深度分析模板
- research: 研究报告模板
"""

from typing import Dict, Any, Optional
import re


# ==================== 快讯模板 ====================
FLASH_TEMPLATE = """
# {title}

**发布时间**：{publish_time}  
**涉及标的**：{stocks}

---

## 核心要点

{summary}

---

## 事件详情

{original_content}

---

## 影响范围

{affected_scope}

---

*本快讯由AI智能生成，仅供参考，不构成投资建议。*
"""


# ==================== 标准新闻模板 ====================
NEWS_TEMPLATE = """
# {title}

{sub_title}

---

**作者**：{author}  
**来源**：{source}  
**发布时间**：{publish_time}  
**涉及标的**：{stocks}

---

## 摘要

{summary}

---

## 正文

{original_content}

---

## 背景解读

{background_analysis}

---

## 市场影响

{market_impact}

---

## 相关标的

{related_stocks}

---

*免责声明：本文内容由AI智能生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
"""


# ==================== 深度分析模板 ====================
ANALYSIS_TEMPLATE = """
# {title}

{sub_title}

---

<div class="article-meta">

**分析师**：{author}  
**发布机构**：{source}  
**发布时间**：{publish_time}  
**报告类型**：深度分析  
**涉及标的**：{stocks}

</div>

---

## 投资摘要

{executive_summary}

---

## 一、事件概述

{event_overview}

### 1.1 事件背景

{background}

### 1.2 核心事实

{core_facts}

---

## 二、深度分析

{deep_analysis}

### 2.1 技术面分析

{technical_analysis}

### 2.2 基本面分析

{fundamental_analysis}

### 2.3 市场情绪

{sentiment_analysis}

---

## 三、影响评估

### 3.1 直接影响

{direct_impact}

### 3.2 间接影响

{indirect_impact}

### 3.3 长期影响

{long_term_impact}

---

## 四、投资建议

{investment_advice}

### 4.1 策略建议

{strategy}

### 4.2 风险提示

{risk_warning}

---

## 五、相关数据

{related_data}

---

**免责声明**

> 本报告由AI智能生成，仅供参考，不构成投资建议。投资者应独立做出投资决策，并自行承担投资风险。过往业绩不代表未来表现，市场有风险，投资需谨慎。

**数据声明**

> 本报告所使用的数据来源于公开渠道，我们力求信息准确，但不对其准确性、完整性作出任何保证。如有侵权，请联系删除。
"""


# ==================== 研究报告模板 ====================
RESEARCH_TEMPLATE = """
# {title}

<div class="research-header">

**研究机构**：{source}  
**分析师**：{author}  
**报告日期**：{publish_time}  
**评级**：{rating}  
**目标价**：{target_price}  
**当前价**：{current_price}  
**涉及标的**：{stocks}

</div>

---

## 投资要点

{key_points}

---

## 核心逻辑

{core_logic}

---

## 详细分析

{detailed_analysis}

---

## 盈利预测

{earnings_forecast}

---

## 估值分析

{valuation_analysis}

---

## 风险提示

{risk_factors}

---

**评级说明**

| 评级 | 定义 |
|------|------|
| 买入 | 预期未来6-12个月内相对同期基准指数涨幅超过20% |
| 增持 | 预期未来6-12个月内相对同期基准指数涨幅在10%-20%之间 |
| 中性 | 预期未来6-12个月内相对同期基准指数涨幅在-10%-10%之间 |
| 减持 | 预期未来6-12个月内相对同期基准指数跌幅超过10% |

---

**免责声明**

> 本报告仅供参考，不构成投资建议。投资者应根据自身风险承受能力谨慎决策。
"""


# ==================== 模板引擎 ====================

TEMPLATES = {
    "flash": FLASH_TEMPLATE,
    "news": NEWS_TEMPLATE,
    "analysis": ANALYSIS_TEMPLATE,
    "research": RESEARCH_TEMPLATE,
}


def get_template(template_name: str) -> str:
    """
    获取指定名称的模板
    
    Args:
        template_name: 模板名称 (flash/news/analysis/research)
    
    Returns:
        模板字符串
    """
    return TEMPLATES.get(template_name, NEWS_TEMPLATE)


def render_template(template: str, context: Dict[str, Any]) -> str:
    """
    渲染模板
    
    Args:
        template: 模板字符串
        context: 模板变量上下文
    
    Returns:
        渲染后的内容
    """
    # 准备默认变量
    default_vars = _prepare_default_vars(context)
    
    # 合并上下文
    render_context = {**default_vars, **context}
    
    # 简单字符串替换
    try:
        result = template.format(**render_context)
    except KeyError as e:
        # 如果有缺失的变量，使用空字符串填充
        missing_key = str(e).strip("'")
        render_context[missing_key] = ""
        result = template.format(**render_context)
    
    return result


def _prepare_default_vars(context: Dict[str, Any]) -> Dict[str, Any]:
    """准备默认模板变量"""
    from datetime import datetime
    
    # 提取分析师数据
    analyst_data = context.get("analyst", {})
    
    # 提取事件数据
    event_data = context.get("event", {})
    
    # 提取标签数据
    label_data = context.get("labels", {})
    
    # 提取NER数据
    ner_data = context.get("ner", {})
    
    # 构建股票列表字符串
    stocks = _format_stocks(ner_data.get("entities", []))
    
    # 构建影响范围
    affected_scope = _format_affected_scope(event_data.get("affected_scope", {}))
    
    # 构建摘要
    summary = _extract_summary(analyst_data)
    
    # 构建投资摘要
    executive_summary = _extract_executive_summary(analyst_data)
    
    # 构建技术分析
    technical_analysis = analyst_data.get("TechnicalAgent", "")
    if isinstance(technical_analysis, dict):
        technical_analysis = technical_analysis.get("content", "")
    
    # 构建基本面分析
    fundamental_analysis = analyst_data.get("FundamentalAgent", "")
    if isinstance(fundamental_analysis, dict):
        fundamental_analysis = fundamental_analysis.get("content", "")
    
    # 构建深度分析
    deep_analysis = "\n\n".join([
        f"### {k}\n{v}" if isinstance(v, str) else f"### {k}\n{str(v)}"
        for k, v in analyst_data.items()
        if k not in ["title", "summary"]
    ])
    
    vars_dict = {
        # 基本信息
        "title": _extract_title(analyst_data, context.get("original_content", "")),
        "sub_title": summary[:100] if summary else "",
        "author": "AI财经助手",
        "source": "AI智能分析",
        "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stocks": stocks,
        
        # 内容
        "original_content": context.get("original_content", ""),
        "summary": summary,
        "executive_summary": executive_summary,
        
        # 分析内容
        "event_overview": event_data.get("event_id", ""),
        "background": "",
        "core_facts": _format_relations(event_data.get("relations", [])),
        "deep_analysis": deep_analysis,
        "technical_analysis": technical_analysis,
        "fundamental_analysis": fundamental_analysis,
        "sentiment_analysis": "",
        
        # 影响
        "affected_scope": affected_scope,
        "direct_impact": "",
        "indirect_impact": "",
        "long_term_impact": "",
        "market_impact": "",
        "background_analysis": "",
        
        # 投资
        "investment_advice": "",
        "strategy": "",
        "risk_warning": "",
        "related_stocks": stocks,
        "related_data": "",
        
        # 研报专用
        "rating": "",
        "target_price": "",
        "current_price": "",
        "key_points": "",
        "core_logic": "",
        "detailed_analysis": deep_analysis,
        "earnings_forecast": "",
        "valuation_analysis": fundamental_analysis,
        "risk_factors": "",
    }
    
    return vars_dict


def _format_stocks(entities: list) -> str:
    """格式化股票列表"""
    stocks = []
    seen = set()
    
    for entity in entities:
        if entity.get("type") in ["STOCK_CODE", "COMPANY"]:
            code = entity.get("stock_code", "")
            name = entity.get("normalized_name") or entity.get("text", "")
            
            if name and name not in seen:
                seen.add(name)
                if code:
                    stocks.append(f"{name}({code})")
                else:
                    stocks.append(name)
    
    return "、".join(stocks) if stocks else "暂无"


def _format_affected_scope(affected_scope: dict) -> str:
    """格式化影响范围"""
    parts = []
    
    if affected_scope.get("macro_areas"):
        parts.append(f"**宏观领域**：{', '.join(affected_scope['macro_areas'])}")
    
    if affected_scope.get("industries"):
        parts.append(f"**受影响行业**：{', '.join(affected_scope['industries'])}")
    
    if affected_scope.get("stocks"):
        parts.append(f"**相关个股**：{', '.join(affected_scope['stocks'][:10])}")
    
    if affected_scope.get("indices"):
        parts.append(f"**相关指数**：{', '.join(affected_scope['indices'])}")
    
    return "\n\n".join(parts) if parts else "暂无详细影响范围数据"


def _format_relations(relations: list) -> str:
    """格式化关系"""
    if not relations:
        return "暂无详细数据"
    
    lines = []
    for rel in relations:
        subject = rel.get("subject", "")
        predicate = rel.get("predicate", "")
        obj = rel.get("object", "")
        value = rel.get("value", "")
        
        line = f"- **{subject}** {predicate} **{obj}**"
        if value:
            line += f"，数值：{value}"
        lines.append(line)
    
    return "\n".join(lines)


def _extract_title(analyst_data: dict, original_content: str) -> str:
    """提取标题"""
    # 尝试从分析师数据中获取
    for key, value in analyst_data.items():
        if isinstance(value, dict):
            title = value.get("title") or value.get("标题")
            if title:
                return title
    
    # 从原始内容提取前20字
    if original_content:
        return original_content[:30] + "..." if len(original_content) > 30 else original_content
    
    return "财经新闻分析"


def _extract_summary(analyst_data: dict) -> str:
    """提取摘要"""
    for key, value in analyst_data.items():
        if isinstance(value, dict):
            summary = value.get("summary") or value.get("摘要") or value.get("执行摘要")
            if summary:
                return summary
            # 尝试从第一个分析结果提取
            for k, v in value.items():
                if isinstance(v, str) and len(v) < 500:
                    return v
    
    return ""


def _extract_executive_summary(analyst_data: dict) -> str:
    """提取投资摘要"""
    summaries = []
    
    for key, value in analyst_data.items():
        if isinstance(value, dict):
            # 查找执行摘要或投资建议
            exec_sum = value.get("执行摘要") or value.get("投资建议") or value.get("投资摘要")
            if exec_sum:
                if isinstance(exec_sum, str):
                    summaries.append(f"**{key}**：{exec_sum}")
                elif isinstance(exec_sum, dict):
                    rating = exec_sum.get("评级", "")
                    advice = exec_sum.get("建议", "")
                    if rating or advice:
                        summaries.append(f"**{key}**：{rating} - {advice}")
    
    return "\n\n".join(summaries) if summaries else "暂无投资建议"


# 注册自定义模板
def register_template(name: str, template: str):
    """注册自定义模板"""
    TEMPLATES[name] = template
