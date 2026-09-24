from recommender.news_reader.agents.analyst.symbol.high_dividend_analyst import prompt_high_dividend
from recommender.news_reader.agents.analyst.symbol.highlow52_analyst import prompt_highlow52
from recommender.news_reader.agents.analyst.industry_analyst import prompt_industry
from recommender.news_reader.agents.analyst.macro_analyst import prompt_macro
from recommender.news_reader.agents.analyst.micro_analyst import prompt_micro
from recommender.news_reader.agents.analyst.portfolio_analyst import prompt_portfolio
from recommender.news_reader.agents.analyst.price_fluctuation_analyst import prompt_price_fluctuation
from recommender.news_reader.agents.analyst.repurchase_analyst import prompt_repurchase
from recommender.news_reader.agents.analyst.risk_analyst import prompt_risk
from recommender.news_reader.agents.analyst.sentiment_analyst import prompt_sentiment
from recommender.news_reader.agents.analyst.symbol.technical_analyst import prompt_technical
from recommender.news_reader.agents.analyst.symbol.fundamental_analyst import prompt_fundamental
from recommender.news_reader.agents.analyst.valuation_analyst import prompt_valuation

_Mapping = {
    "MacroAgent": prompt_macro(),
    "IndustryAgent": prompt_industry(),
    "MicroAgent": prompt_micro(),
    "EventAgent": prompt_repurchase(),
    "ValuationAgent": prompt_valuation(),
    "TechnicalAgent": prompt_technical(),
    "TechnicalHLAgent": prompt_highlow52(),
    "SentimentAgent": prompt_sentiment(),
    "DividendAgent": prompt_high_dividend(),
    "FundamentalAgent": prompt_fundamental(),
    "PortfolioAgent": prompt_portfolio(),
    "RiskAgent": prompt_risk(),
}

_MappingName = {
    "MacroAgent":        "宏观经济分析（IS-LM、AD-AS、传导机制）",
    "IndustryAgent":     "行业分析（五维打分、景气周期、产业链）",
    "MicroAgent":        "公司微观分析（波特五力、SWOT、财务穿透）",
    "EventAgent":        "事件驱动分析（回购、并购、定增、诉讼定价）",
    "ValuationAgent":    "估值分析（DCF、PE/PB、风险溢价）",
    "TechnicalAgent":    "技术分析（趋势/支撑阻力/指标/形态/量价）",
    "TechnicalHLAgent":  "技术分析-52周高低点策略",
    "SentimentAgent":    "情绪与资金流向分析",
    "DividendAgent":     "股息策略分析",
    "FundamentalAgent":  "基本面分析（财务/盈利/成长/估值/治理）",
    "PortfolioAgent":    "组合影响分析（持仓冲击、调仓建议）",
    "RiskAgent":         "风险预警与压力测试",
}


def create_analyst(name: str):
    if name in _Mapping:
        return _Mapping[name], _MappingName[name]
    else:
        return "", ""

