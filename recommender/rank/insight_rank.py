"""

"""


import json
from typing import List, Dict, Any


def rank_news(
    user_profile: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 5,
) -> str:
    """
    构建财经新闻 LLM 重排序的 Prompt，直接返回 prompt 字符串。
    """

    def serialize_candidate(c: Dict[str, Any]) -> str:
        pt = c.get("publish_time", "")
        if isinstance(pt, str) and "T" in pt:
            pt = pt[11:16] if len(pt) > 16 else pt

        depth_tags = []
        if c.get("has_industry_report") or c.get("has_micro_analysis"):
            depth_tags.append("深度研报")
        if c.get("depth_type") == "deep_analysis":
            depth_tags.append("深度分析")
        if c.get("depth_type") == "flash":
            depth_tags.append("快讯")

        return json.dumps({
            "id": c.get("id"),
            "headline": c.get("headline", ""),
            "category": c.get("category", ""),
            "entities": c.get("entities", []),
            "time": pt,
            "sentiment": c.get("sentiment", ""),
            "depth": depth_tags,
            "recall_reason": c.get("recall_reason", ""),
            "freshness_score": c.get("freshness_score", 1.0),
        }, ensure_ascii=False, indent=None)

    candidates_json = ",\n".join([serialize_candidate(c) for c in candidates[:20]])

    prompt = f"""你是一位资深财经资讯编辑，负责为用户精选最值得阅读的财经新闻。

## 用户画像
{user_profile}

## 排序原则（按优先级降序）
1. **持仓相关优先**：用户持有特定标的时，涉及该标的的深度分析类新闻必须进入Top-3，但需控制频次避免过载
2. **时效优先**：publish_time越近权重越高，超过6小时的新闻需有强理由才进Top-{top_k}
3. **兴趣匹配**：契合用户新闻偏好标签（如POLICY_REGULATION_WATCHER、SECTOR_ROTATION_TRACKER）
4. **疲劳控制**：近24小时已读多次的同类主题/实体必须降级；单一实体在Top-{top_k}中最多出现2次
5. **深度适配**：DEEP_DIVE_READER优先有深度分析（深度研报/深度分析标签）的长文，避免纯快讯
6. **多样性**：Top-{top_k}至少覆盖3个不同category，不能全是宏观或全是科技/个股
7. **信息增量**：优先用户"未读高兴趣"领域，填补信息缺口

## 候选新闻列表（共{len(candidates)}篇）
[{candidates_json}]

## 任务
从候选列表中选出Top {top_k}，按阅读优先级排序。

对每篇输出：
- `id`: 新闻ID
- `rank`: 1-{top_k}
- `score`: 0-100 匹配度
- `reason`: 推荐理由（25-40字，直接面向用户，说明"为什么你现在该看这篇"）
- `fatigue_check`: 是否触发疲劳降权（true/false）
- `diversity_tag`: 该篇覆盖的维度（如 ["持仓相关", "政策", "深度分析"]）

## 输出格式（严格JSON，不要markdown代码块标记，直接输出JSON对象）
{{
  "top_{top_k}": [
    {{
      "id": "news_xxx",
      "rank": 1,
      "score": 95,
      "reason": "...",
      "fatigue_check": false,
      "diversity_tag": ["...", "..."]
    }}
  ],
  "diversity_summary": {{
    "categories_covered": ["公司事件", "宏观", "行业"],
    "fatigue_alert": "..."
  }},
  "logic_note": "整体排序逻辑：..."
}}"""

    return prompt