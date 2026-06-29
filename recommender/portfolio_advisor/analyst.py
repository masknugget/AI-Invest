"""
投资组合核心风险提示生成示例

用法：
    python research/portfolio_advisor/analyst.py

流程：
    1. 根据资产权重与行业分布构造风控专家 Prompt。
    2. 调用 LLM 生成 2-3 条核心风险提示（JSON 列表格式）。
    3. 打印模型原始返回，便于进一步解析或展示。
"""

import json
from typing import Any, Dict, List, Optional

from research.newsReader.llms import chat_once


RiskItem = Dict[str, str]


def build_risk_prompt(weights: List[float], industry_dist: Dict[str, float]) -> str:
    """
    构造“核心风险提示”专家 Prompt。

    参数
    ----------
    weights : List[float]
        各资产权重，长度与资产数量一致，加和应为 1。
    industry_dist : Dict[str, float]
        行业分布，key 为行业名称，value 为该行业占比。

    返回
    -------
    str
        可直接送入 LLM 的完整提示词。
    """
    return f"""
# 任务

# 角色与任务
你是一位严谨的量化策略风控专家，信奉“先求不败，再求胜”的理念。请根据提供的<量化策略评估体系>和<输入数据>，为用户生成“核心风险提示”。

# 量化策略评估体系
**核心理念**：先求不败，再求胜。65%权重配置于风险维度，强调风险调整后收益与生存优先。

**五个维度**：
- `drawdown_control`（回撤控制，25%）：衡量最大回撤与恢复能力。90-100分对应MDD<5%；70-89分为5-15%；50-69分为15-25%；30-49分为25-40%；0-29分则>40%，面临清盘风险。
- `return_stability`（收益稳定性，20%）：衡量年化波动率与月度胜率。90-100分波动<5%；70-89分5-10%；50-69分10-20%；30-49分20-35%；0-29分>35%，收益脉冲剧烈。
- `position_efficiency`（持仓效率，25%）：衡量夏普、信息比率。90-100分夏普>2；70-89分1.5-2；50-69分1-1.5；30-49分0.5-1；0-29分<0.5，收益性价比极低。
- `portfolio_diversification`（分散度，15%）：衡量持仓集中度与相关性。90-100分平均相关系数<0.3；70-89分0.3-0.5；50-69分0.5-0.7；30-49分0.7-0.9；0-29分>0.9，高度集中。
- `style_balance`（风格平衡，15%）：衡量因子暴露与Beta。90-100分暴露<0.5σ；70-89分0.5-1σ；50-69分1-2σ；30-49分>2σ；0-29分风格漂移严重。

# 输入数据
资产权重: {weights}
行业分布: {industry_dist}

# 输出要求
1. 提取2-3个基于当前输入数据最致命的风险点（需结合评估体系中的分散度、回撤控制等维度）。
2. 格式需严格参考示例：标题为4-8个字的简短概括，换行后附上一句话的具体说明（包含数据现象及对账户的后果）。
3. 语气客观、专业，直击痛点。

# 示例
[
    {{"summary": "行业过度重叠", "detail":"你有 42% 的资产集中在"消费与白酒"领域。若大消费板块走弱，你的账户将承受巨大压力。"}},
    {{"summary": "高波动资产占比过高", "detail":"权益类资产波动率超过 25%，超出了新手用户的一般心理承受能力。"}}
]

# 开始生成
请根据输入数据，直接输出“核心风险提示”及具体内容。

# 格式要求
[
    {{"summary": "***", "detail":"***"}},
    {{"summary": "***", "detail":"***"}}
]
"""


def generate_risks(weights: List[float], industry_dist: Dict[str, float]) -> Optional[str]:
    """
    调用 LLM 生成核心风险提示文本。

    返回
    -------
    Optional[str]
        模型返回的 JSON 字符串；若调用失败则返回 None。
    """
    prompt = build_risk_prompt(weights, industry_dist)
    return chat_once(prompt)


def parse_risks(raw: Optional[str]) -> List[RiskItem]:
    """
    简单解析模型返回的 JSON 风险提示列表。

    若解析失败，则返回空列表，并把原始文本打印出来便于排查。
    """
    if not raw:
        return []

    # 先尝试直接解析；若模型包裹了 ```json ... ```，则提取中间内容。
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data: Any = json.loads(text)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except json.JSONDecodeError:
        print("[warn] JSON 解析失败，原始输出如下：")
        print(raw)

    return []


if __name__ == "__main__":
    # 示例输入：3 只资产的权重与行业分布
    sample_weights = [0.4, 0.35, 0.25]
    sample_industry = {
        "消费/白酒": 0.40,
        "医药生物": 0.35,
        "新能源": 0.25,
    }

    print("=" * 70)
    print("示例输入")
    print(f"资产权重: {sample_weights}")
    print(f"行业分布: {sample_industry}")
    print("=" * 70)

    raw_output = generate_risks(sample_weights, sample_industry)
    if raw_output is None:
        print("调用 LLM 失败，未获取到风险提示。")
    else:
        risks = parse_risks(raw_output)
        if risks:
            print("\n核心风险提示：")
            for idx, risk in enumerate(risks, start=1):
                summary = risk.get("summary", "")
                detail = risk.get("detail", "")
                print(f"{idx}. {summary}")
                print(f"   {detail}")
        else:
            print("\n模型原始输出：")
            print(raw_output)
