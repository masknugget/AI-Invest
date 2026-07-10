from app.core.db import get_stock_data
from recommender.news_reader.llms import chat_once
from recommender.portfolio_advisor.analyst import generate_risks, parse_risks, prompt_comprehensive
from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions
from recommender.portfolio_advisor.format_adapt.format_dimensions import format_dimensions

codes = ["000001", "000002", "000003"]
weights = [0.3, 0.3, 0.4]


df = get_stock_data(codes[0], start_date='2020-01-01', end_date='2026-01-01')
df_1 = get_stock_data(codes[1], start_date='2020-01-01', end_date='2026-01-01')
df_2 = get_stock_data(codes[2], start_date='2020-01-01', end_date='2026-01-01')


dfs = [df, df_1, df_2]
# 5维度透视表
result = compute_portfolio_dimensions(dfs, weights)

# 核心风险提示
sample_industry = {
    "Specialty Retailers": 0.7,
    "Natural Gas Utilities": 0.3,
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

formatted = format_dimensions(result)

