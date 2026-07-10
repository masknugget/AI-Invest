"""
五维诊断独立示例。

用法：
    python research/portfolio_advisor/examples/dimensions_example.py

流程：
    1. 随机抽取 5 只标的并指定权重。
    2. 调用 compute_portfolio_dimensions 计算五维得分与综合分。
    3. 打印结果。
"""

from typing import Any, List

from pathlib import Path
import pandas as pd

from app.core.db import save_advisor_result
from recommender.news_reader.llms import chat_once
from recommender.portfolio_advisor.analyst import parse_risks, generate_risks, prompt_comprehensive
from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions
from recommender.portfolio_advisor.format_adapt.format_advisor import (
    format_advisor_result,
    format_dimensions,
    format_report,
    format_risk_alerts,
)


def _unwrap_df(item: Any) -> Any:
    """兼容 FileVisitor 可能返回 (key, df) 元组的情况。"""
    if isinstance(item, tuple):
        return item[1]
    return item



DATA_DIR = Path(r'F:\project_work\hf\AI-Invest\recommender\portfolio_advisor\data')

def _read_parquet(filename: str) -> pd.DataFrame:
    """读取单个 parquet 文件，文件不存在时抛出 FileNotFoundError。"""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    return pd.read_parquet(path)

# 模块级变量：df_1 ~ df_5
df_1 = _read_parquet("df_1.parquet")
df_2 = _read_parquet("df_2.parquet")
df_3 = _read_parquet("df_3.parquet")

dfs = [df_1, df_2, df_3]
weights = [0.3, 0.3, 0.4]
codes = [str(df["code"].iloc[0]) for df in dfs]

# 核心风险提示
sample_industry = {
    "Specialty Retailers": 0.7,
    "Natural Gas Utilities": 0.3,
}

user_id = "admin123"





###########################

print("=== save industry distribution ===")


# 5维度透视表
result = compute_portfolio_dimensions(dfs, weights)


out_dimensions = format_dimensions(result)



raw_output = generate_risks(weights, sample_industry)
risks: list = []
if raw_output is None:
    print("调用 LLM 失败，未获取到风险提示。")
else:
    risks = parse_risks(raw_output)

# 保存起来


score = result.to_score_dict()
# 综合评分
_p = prompt_comprehensive(
    drawdown_control=score["drawdown_control"],
    return_stability=score["portfolio_diversification"],
    position_efficiency=score["position_efficiency"],
    portfolio_diversification=score["portfolio_diversification"],
    style_balance=score["style_balance"],
)
out_data = chat_once(_p)

out_result = parse_risks(out_data)
if not isinstance(out_result, dict):
    out_result = {}

comprehensive_str = out_result.get("text", "")
comprehensive_label = out_result.get("label", "")

out_risk_alert = format_risk_alerts(risks)
out_risk_report = format_report(result, comprehensive_str)

out_advisor_result = format_advisor_result(
    dimensions=out_dimensions,
    risk_report=out_risk_report,
    risk_alert=out_risk_alert,
    industry_distribution=sample_industry,
)

save_advisor_result(out_advisor_result, user_id=user_id)

