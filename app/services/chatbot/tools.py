import json

from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool, convert_to_openai_function


@tool
def search_stock_information(stock_code: str, date_time=None, indicator_name=None) -> dict:
    """
    查找股票信息
    搜索股票价格
    :param stock_code: 输入股票代码或者名称查找相关的信息
    :param date_time: 日期
    :param date_time: 指标名称
    :return:
    """
    pass


@tool
def analyze_stock_information(stock_code: str) -> dict:
    """
    分析股票相关的信息
    :param stock_code:
    :return:
    """
    pass


@tool
def analyze_stock_by_type(stock_code: str, analyze_type: str) -> dict:
    """
    按照analyze类型分析股票
    :param stock_code: 股票代码或者名称
    :param analyze_type: 分析类型，基本面，技术面，新闻面
    :return:
    """
    pass


tools = [search_stock_information, analyze_stock_information, analyze_stock_by_type]

# 批量转换为 OpenAI functions 格式
functions = [convert_to_openai_function(t) for t in tools]


json_tools = json.dumps(functions, indent=2, ensure_ascii=False)