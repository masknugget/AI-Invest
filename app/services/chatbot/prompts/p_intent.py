"""
- 查找股价
    工具调用
    某天股票的信息
    股票某天的价格
    股票某天的技术指标

- 帮我分析一下
    基本面分析
    技术分析
"""


def wrap_intent(
        user_query: str,
        tools: str,
):
    out_data = f"""
# 任务
识别用户意图，同时提取相关的实体

# 实体
code: 股票代码
name: 股票名称
analyze_type: 分析类型（枚举：基本面，技术面，新闻面)
indicator_name: 指标名称（例如收盘价, 股价等）

# 输出格式
统一为function_call的格式

# 用户输入
{user_query}

# 参考工具
 {tools}
"""
    return out_data