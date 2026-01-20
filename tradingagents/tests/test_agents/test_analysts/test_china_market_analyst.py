from tradingagents.agents.analysts.china_market_analyst import create_china_market_analyst
from tradingagents.agents.utils.agent_states import InvestDebateState, RiskDebateState
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.llm_adapters import ChatDashScopeOpenAI

quick_thinking_llm = ChatDashScopeOpenAI(
    model="qwen-plus",
    api_key="sk-12e56ecde21e49029ab895d80f357536",  # 🔥 传递 API Key
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 传递 base_url
    temperature=0.1,
    max_tokens=20000,
    request_timeout=500
)


llm = create_china_market_analyst(
    quick_thinking_llm,
    Toolkit
)

"""Create the initial state for the agent graph."""
from langchain_core.messages import HumanMessage


company_name = "000001"
trade_date = "2025-01-05"

# 🔥 修复：创建明确的分析请求消息，而不是只传递股票代码
# 这样可以确保所有LLM（包括DeepSeek）都能理解任务
analysis_request = f"请对股票 {company_name} 进行全面分析，交易日期为 {trade_date}。"



init_data = {
    "messages": [HumanMessage(content=analysis_request)],
    "company_of_interest": company_name,
    "trade_date": str(trade_date),
    "investment_debate_state": InvestDebateState(
        {"history": "", "current_response": "", "count": 0}
    ),
    "risk_debate_state": RiskDebateState(
        {
            "history": "",
            "current_risky_response": "",
            "current_safe_response": "",
            "current_neutral_response": "",
            "count": 0,
        }
    ),
    "market_report": "",
    "fundamentals_report": "",
    "sentiment_report": "",
    "news_report": "",
}


out_data = llm(init_data)
