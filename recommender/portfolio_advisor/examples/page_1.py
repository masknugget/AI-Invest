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

from recommender.news_reader.llms import chat_once
from recommender.portfolio_advisor.analyst import parse_risks, generate_risks, prompt_comprehensive
from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions


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

# 5维度透视表
result = compute_portfolio_dimensions(dfs, weights)

print("=" * 70)
print("组合标的:", codes)
print("组合权重:", weights)
print("=" * 70)

print("【抗回撤能力】")
print(f"  最大回撤 MDD       : {result.drawdown_control.mdd:.4f}")
print(f"  控制得分 (0-100)   : {result.drawdown_control.score:.2f}")

print("\n【资产分散度】")
print(f"  ENB (weight-based) : {result.portfolio_diversification.enb_weight_based:.4f}")
print(f"  分散得分 (0-100)   : {result.portfolio_diversification.score:.2f}")

print("\n【持仓性价比】")
print(f"  夏普比率           : {result.position_efficiency.sharpe_ratio:.4f}")
print(f"  性价比得分 (0-100) : {result.position_efficiency.score:.2f}")

print("\n【收益稳定性】")
print(f"  年化波动率         : {result.return_stability.annualized_volatility:.4f}")
print(f"  稳定得分 (0-100)   : {result.return_stability.score:.2f}")

print("\n【风格均衡】")
print(f"  风格 HHI           : {result.style_balance.style_hhi:.4f}")
print(f"  均衡得分 (0-100)   : {result.style_balance.score:.2f}")

print("\n" + "=" * 70)
print(f"综合健康分 (0-100)    : {result.composite_score:.2f}")
print(f"几何加权综合分 (0-100) : {result.geometric_composite_score:.2f}")
print("=" * 70)

# 核心风险提示
sample_industry = {
    "消费/白酒": 0.40,
    "医药生物": 0.35,
    "新能源": 0.25,
}

raw_output = generate_risks(weights, sample_industry)
if raw_output is None:
    print("调用 LLM 失败，未获取到风险提示。")
else:
    risks = parse_risks(raw_output)

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

comprehensive_str = out_result['text']
