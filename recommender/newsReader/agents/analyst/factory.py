from research.newsReader.agents.analyst.high_dividend_analyst import prompt_high_dividend
from research.newsReader.agents.analyst.highlow52_analyst import prompt_highlow52
from research.newsReader.agents.analyst.industry_analyst import prompt_industry
from research.newsReader.agents.analyst.macro_analyst import prompt_macro
from research.newsReader.agents.analyst.micro_analyst import prompt_micro
from research.newsReader.agents.analyst.portfolio_analyst import prompt_portfolio
from research.newsReader.agents.analyst.price_fluctuation_analyst import prompt_price_fluctuation
from research.newsReader.agents.analyst.repurchase_analyst import prompt_repurchase
from research.newsReader.agents.analyst.symbol.technical_analyst import prompt_technical
from research.newsReader.agents.analyst.symbol.fundamental_analyst import prompt_fundamental

_Mapping = {
    "MacroAgent": prompt_macro(),
    "IndustryAgent": prompt_industry(),
    "MicroAgent": prompt_micro(),
    "EventAgent": prompt_repurchase(),
    "ValuationAgent": prompt_micro(),
    "TechnicalAgent": prompt_technical(),
    "TechnicalHLAgent": prompt_highlow52(),
    "SentimentAgent": prompt_micro(),
    "DividendAgent": prompt_high_dividend(),
    "FundamentalAgent": prompt_fundamental(),
    "PortfolioAgent": prompt_portfolio(),
    "RiskAgent": "风险预警与压力测试",
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

