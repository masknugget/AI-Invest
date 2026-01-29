from tradingagents.graph import TradingAgentsGraph

config = {'backend_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
          'data_cache_dir': r'G:\git_data\AI-Invest\tradingagents\dataflows/data_cache',
          'data_dir': r'C:\Users\94688\Documents\TradingAgents\data', 'debug': False,
          'deep_api_key': 'sk-12e56ecde21e49029ab895d80f357536',
          'deep_backend_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'deep_provider': 'dashscope',
          'deep_think_llm': 'qwen-max', 'llm_provider': 'dashscope', 'max_debate_rounds': 1, 'max_recur_limit': 10,
          'max_risk_discuss_rounds': 1, 'memory_enabled': True, 'online_news': True, 'online_tools': True,
          'project_dir': r'G:\git_data\AI-Invest\tradingagents', 'quick_api_key': 'sk-12e56ecde21e49029ab895d80f357536',
          'quick_backend_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'quick_provider': 'dashscope',
          'quick_think_llm': 'qwen-turbo', 'realtime_data': False, 'research_depth': '标准', 'results_dir': './results',
          'selected_analysts': ['market'], 'language': 'en-US'}


trading_graph = TradingAgentsGraph(
    selected_analysts=config.get("selected_analysts", ["market", "fundamentals", "news"]),
    debug=config.get("debug", False),
    config=config
)

stock_code = "000001"
analysis_date = "2025-10-01"
state, decision = trading_graph.propagate(
    stock_code,
    analysis_date,
    language = 'en-US',
)
