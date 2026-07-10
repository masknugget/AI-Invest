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

from recommender.news_reader.llms import chat_once

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


def parse_risks(raw: Optional[str]):
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
        return data
    except json.JSONDecodeError:
        print("[warn] JSON 解析失败，原始输出如下：")
        print(raw)

    return []


def build_rebalance_reason_prompt(
    code_out: Optional[str],
    code_in: Optional[str],
    weight_out: float,
    weight_in: float,
    score_before: float,
    score_after: float,
    improvement: float,
    scores_out: Optional[Dict[str, float]] = None,
    scores_in: Optional[Dict[str, float]] = None,
    objective: str = "composite_score",
) -> str:
    """构造调仓动作详细原因说明的 Prompt。"""
    scores_out_str = json.dumps(scores_out, ensure_ascii=False, indent=2) if scores_out else "无"
    scores_in_str = json.dumps(scores_in, ensure_ascii=False, indent=2) if scores_in else "无"
    return f"""
# 角色
你是一位专业的量化投资顾问，擅长根据五维评分解释调仓决策。

# 任务
请根据以下调仓动作信息，以及调出、调入股票的五维评分，生成一段详细的调入/调出原因说明。

# 五维评分说明
- drawdown_control（回撤控制）：得分越高，抗回撤能力越强
- portfolio_diversification（分散度）：得分越高，组合分散效果越好
- position_efficiency（持仓效率）：得分越高，风险调整后收益越好
- return_stability（收益稳定性）：得分越高，波动越小
- style_balance（风格均衡）：得分越高，风格暴露越均衡

# 输入数据
- 调出股票: {code_out or "无"}
- 调出股票五维评分:
{scores_out_str}
- 调入股票: {code_in or "无"}
- 调入股票五维评分:
{scores_in_str}
- 调出前权重: {weight_out:.4f}
- 调入后权重: {weight_in:.4f}
- 调仓前得分: {score_before:.4f}
- 调仓后得分: {score_after:.4f}
- 得分提升: {improvement:.4f}
- 优化目标: {objective}

# 输出要求
请重点对比调出股票和调入股票在五维评分上的差异，解释为什么这次替换能提升组合得分。
不要直接输出数值，应该是说明效果，比如降低回撤，引入更稳健资产，降低集中度等利于理解的表达。
生成一段 30-90 字的说明，直接输出文本，不要输出 JSON 或 Markdown 代码块。
"""


def reason_llm(
    code_out: Optional[str],
    code_in: Optional[str],
    weight_out: float,
    weight_in: float,
    score_before: float,
    score_after: float,
    improvement: float,
    scores_out: Optional[Dict[str, float]] = None,
    scores_in: Optional[Dict[str, float]] = None,
    objective: str = "composite_score",
) -> Optional[str]:
    """
    调用 LLM 生成调仓动作的详细原因说明。

    参数
    ----------
    code_out, code_in : 调出/调入股票代码
    weight_out, weight_in : 调出/调入权重
    score_before, score_after : 调仓前后得分
    improvement : 得分提升
    scores_out, scores_in : 调出/调入股票的五维评分字典
    objective : 优化目标

    返回
    -------
    Optional[str]
        模型返回的文本；若调用失败则返回 None。
    """
    prompt = build_rebalance_reason_prompt(
        code_out=code_out,
        code_in=code_in,
        weight_out=weight_out,
        weight_in=weight_in,
        score_before=score_before,
        score_after=score_after,
        improvement=improvement,
        scores_out=scores_out,
        scores_in=scores_in,
        objective=objective,
    )
    try:
        return chat_once(prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] reason_llm 调用失败: {exc}")
        return None


def prompt_comprehensive(
        drawdown_control,
        return_stability,
        position_efficiency,
        portfolio_diversification,
        style_balance,
):
    data_str = f"""
    
    # 任务
    给定一个组合的如下指标
    进行评价，或者总结，也可使或是诊断
    
    # 指标
    drawdown_control: {drawdown_control}
    return_stability: {return_stability}
    position_efficiency: {position_efficiency}
    portfolio_diversification: {portfolio_diversification}
    style_balance： {style_balance}
    
    # 输出格式
    {{
        "text": ***,
        "label": ***,
    }}
    其中label为良好，亚健康等诊断词汇
    
    # 字数要求
    在20-80字之间
    """
    return data_str


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
