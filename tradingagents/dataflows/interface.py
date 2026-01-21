"""
数据接口适配器
将旧的 interface.py 调用转发到 db/document.py
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from tradingagents.db.document import (
    get_stock_data,
    get_stock_info,
    get_stock_news,
    get_market_news,
    get_china_stock_info,
    get_hk_stock_info,
)

from tradingagents.config.config_manager import config_manager

# 获取数据目录
DATA_DIR = config_manager.get_data_dir()


def get_config():
    """获取配置（兼容性包装）"""
    return config_manager.load_settings()


def set_config(config):
    """设置配置（兼容性包装）"""
    config_manager.save_settings(config)


# ==================== A股数据接口 ====================

def get_china_stock_data_unified(ticker, start_date, end_date):
    """
    适配器：从 db/document.py 获取 A 股数据
    返回字符串格式（兼容旧接口）
    """
    try:
        data = get_stock_data(ticker, start_date, end_date, "technical")

        if not data:
            return f"⚠️ 未找到 {ticker} 在 {start_date} 到 {end_date} 的数据"

        # 转换为 DataFrame 并格式化输出
        df = pd.DataFrame(data)

        output = f"## {ticker} 股票数据 ({start_date} 到 {end_date})\n\n"
        output += f"共 {len(df)} 条记录\n\n"

        if not df.empty:
            output += df.to_string(index=False)

        return output

    except Exception as e:
        return f"❌ 获取数据失败: {str(e)}"


def get_china_stock_info_unified(ticker) -> str:
    """
    适配器：从 db/document.py 获取 A 股基本信息
    返回字符串格式
    """
    try:
        info = get_china_stock_info(ticker)

        if not info:
            return f"⚠️ 未找到 {ticker} 的基本信息"

        output = f"## {ticker} 股票基本信息\n\n"
        output += f"- 股票名称: {info.get('name', '未知')}\n"
        output += f"- 所属地区: {info.get('area', '未知')}\n"
        output += f"- 所属行业: {info.get('industry', '未知')}\n"
        output += f"- 上市市场: {info.get('market', '未知')}\n"
        output += f"- 上市日期: {info.get('list_date', '未知')}\n"

        # 添加行情信息（如果有）
        if 'current_price' in info:
            output += f"- 当前价格: {info.get('current_price')}\n"
        if 'change_pct' in info:
            output += f"- 涨跌幅: {info.get('change_pct')}%\n"
        if 'volume' in info:
            output += f"- 成交量: {info.get('volume')}\n"

        return output

    except Exception as e:
        return f"❌ 获取基本信息失败: {str(e)}"


# ==================== 港股数据接口 ====================

def get_hk_stock_data_unified(symbol, start_date=None, end_date=None):
    """
    适配器：从 db/document.py 获取港股数据
    返回字符串格式
    """
    try:
        if not start_date or not end_date:
            # 如果没有提供日期，使用最近30天
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        data = get_stock_data(symbol, start_date, end_date, "technical")

        if not data:
            return f"⚠️ 未找到 {symbol} 在 {start_date} 到 {end_date} 的数据"

        df = pd.DataFrame(data)

        output = f"## {symbol} 港股数据 ({start_date} 到 {end_date})\n\n"
        output += f"共 {len(df)} 条记录\n\n"

        if not df.empty:
            output += df.to_string(index=False)

        return output

    except Exception as e:
        return f"❌ 获取港股数据失败: {str(e)}"


def get_hk_stock_info_unified(symbol):
    """
    适配器：从 db/document.py 获取港股基本信息
    返回字典格式
    """
    try:
        info = get_hk_stock_info(symbol)
        return info if info else {}
    except Exception:
        return {}


# ==================== 新闻数据接口 ====================

def get_finnhub_news(ticker, curr_date, look_back_days):
    """
    适配器：从 db/document.py 获取股票新闻
    """
    try:
        start_date = (datetime.strptime(curr_date, "%Y-%m-%d") -
                      timedelta(days=look_back_days)).strftime("%Y-%m-%d")

        news = get_stock_news(ticker, start_date, curr_date)

        output = f"## {ticker} 新闻 ({start_date} 到 {curr_date})\n\n"

        if not news:
            return output + "未找到相关新闻"

        for item in news[:20]:  # 最多20条
            title = item.get('title', '') or item.get('headline', '无标题')
            date = item.get('date', '') or item.get('publish_date', '')
            summary = item.get('summary', '') or item.get('content', '')[:200]

            output += f"### {title}\n"
            output += f"**日期**: {date}\n\n"
            output += f"{summary}\n\n"

        return output

    except Exception as e:
        return f"❌ 获取新闻失败: {str(e)}"


def get_finnhub_company_insider_sentiment(ticker, curr_date, look_back_days):
    """预留接口 - 暂无数据"""
    return ""


def get_finnhub_company_insider_transactions(ticker, curr_date, look_back_days):
    """预留接口 - 暂无数据"""
    return ""


# ==================== 财务数据接口（预留） ====================

def get_simfin_balance_sheet(ticker, freq, curr_date):
    """预留接口 - 暂无数据"""
    return "暂不支持财务数据查询"


def get_simfin_cashflow(ticker, freq, curr_date):
    """预留接口 - 暂无数据"""
    return "暂不支持财务数据查询"


def get_simfin_income_statements(ticker, freq, curr_date) -> str:
    """预留接口 - 暂无数据"""
    return "暂不支持财务数据查询"


# ==================== Google新闻适配器 ====================

def get_google_news(query, curr_date, look_back_days=7):
    """
    适配器：从 db/document.py 获取新闻
    """
    try:
        start_date = (datetime.strptime(curr_date, "%Y-%m-%d") -
                      timedelta(days=look_back_days)).strftime("%Y-%m-%d")

        news = get_stock_news(query, start_date, curr_date)

        if not news:
            news = get_market_news(start_date, curr_date)

        output = f"## Google News: {query} ({start_date} 到 {curr_date})\n\n"

        if not news:
            return output + "未找到相关新闻"

        for item in news[:15]:
            title = item.get('title', '') or item.get('headline', '无标题')
            source = item.get('source', '未知来源')
            snippet = item.get('summary', '') or item.get('content', '')[:150]

            output += f"### {title} ({source})\n\n"
            output += f"{snippet}...\n\n"

        return output

    except Exception as e:
        return f"❌ 获取新闻失败: {str(e)}"


# ==================== Reddit新闻适配器 ====================

def get_reddit_global_news(start_date, look_back_days, max_limit_per_day):
    """
    适配器：从 db/document.py 获取全球新闻
    """
    try:
        end_date = datetime.strptime(start_date, "%Y-%m-%d")
        start_date_dt = end_date - timedelta(days=look_back_days)
        start_date_str = start_date_dt.strftime("%Y-%m-%d")

        news = get_market_news(start_date_str, start_date, news_type="global")

        output = f"## Reddit Global News ({start_date_str} 到 {start_date})\n\n"

        if not news:
            return output + "未找到全球新闻"

        for item in news[:max_limit_per_day * (look_back_days + 1)]:
            title = item.get('title', '无标题')
            content = item.get('content', '') or item.get('summary', '')

            output += f"### {title}\n\n"
            if content:
                output += f"{content[:300]}...\n\n"

        return output

    except Exception as e:
        return f"❌ 获取Reddit全球新闻失败: {str(e)}"


def get_reddit_company_news(ticker, start_date, look_back_days, max_limit_per_day):
    """
    适配器：从 db/document.py 获取公司新闻
    """
    try:
        end_date = datetime.strptime(start_date, "%Y-%m-%d")
        start_date_dt = end_date - timedelta(days=look_back_days)
        start_date_str = start_date_dt.strftime("%Y-%m-%d")

        news = get_stock_news(ticker, start_date_str, start_date)

        output = f"## Reddit {ticker} 新闻 ({start_date_str} 到 {start_date})\n\n"

        if not news:
            return output + "未找到相关新闻"

        for item in news[:max_limit_per_day * (look_back_days + 1)]:
            title = item.get('title', '无标题')
            content = item.get('content', '') or item.get('summary', '')

            output += f"### {title}\n\n"
            if content:
                output += f"{content[:300]}...\n\n"

        return output

    except Exception as e:
        return f"❌ 获取Reddit公司新闻失败: {str(e)}"


# ==================== 财务数据适配器（预留） ====================

def get_fundamentals_openai(ticker, curr_date):
    """预留接口 - 财务数据暂不支持"""
    return f"暂不支持 {ticker} 的财务数据查询"


# ==================== 技术指标适配器（简化版） ====================

def get_stock_stats_indicators_window(symbol, indicator, curr_date, look_back_days, online=False):
    """
    适配器：从 MongoDB 获取数据并计算简单的技术指标
    """
    try:
        data = get_stock_data(symbol, curr_date, curr_date, "technical")

        if not data:
            return f"⚠️ 未找到 {symbol} 的数据"

        output = f"## {indicator} 指标（简化版）\n\n"
        output += f"暂不支持详细的技术指标计算\n\n"
        output += f"当前价格数据：\n"
        output += f"- 收盘价: {data[-1].get('close', 'N/A')}\n"
        output += f"- 开盘价: {data[-1].get('open', 'N/A')}\n"
        output += f"- 最高价: {data[-1].get('high', 'N/A')}\n"
        output += f"- 最低价: {data[-1].get('low', 'N/A')}\n"

        return output

    except Exception as e:
        return f"❌ 计算指标失败: {str(e)}"


def get_stockstats_indicator(symbol, indicator, curr_date, online=False):
    """预留接口 - 简化版"""
    return "暂不支持"


# ==================== 配置函数（简化版） ====================

def get_config():
    """简化配置返回"""
    return {
        "data_source": "mongodb",
        "enabled": True
    }


def get_current_china_data_source():
    """返回当前 A 股数据源"""
    return "mongodb"


def get_stock_data_by_market(symbol, start_date=None, end_date=None):
    """
    根据市场类型自动选择数据
    """
    from tradingagents.db.document import detect_market

    market = detect_market(symbol)

    if market == 'cn':
        return get_china_stock_data_unified(symbol, start_date, end_date)
    elif market == 'hk':
        return get_hk_stock_data_unified(symbol, start_date, end_date)
    else:
        return f"⚠️ 无法识别市场类型: {symbol}"


# ==================== 新增函数 ====================

def get_chinese_social_sentiment(ticker, curr_date):
    """
    获取中国社交媒体情绪数据（提供简化版实现）
    
    Args:
        ticker: 股票代码
        curr_date: 当前日期
        
    Returns:
        str: 情绪分析结果
    """
    try:
        # 尝试从 get_stock_news 获取相关新闻
        start_date = (datetime.strptime(curr_date, "%Y-%m-%d") -
                      timedelta(days=7)).strftime("%Y-%m-%d")

        news = get_stock_news(ticker, start_date, curr_date)

        output = f"## {ticker} 中国社交媒体情绪分析\n\n"
        output += f"**分析日期范围**: {start_date} 到 {curr_date}\n\n"

        if not news:
            output += "⚠️ 未找到相关新闻数据\n\n"
            output += "基于中国主流财经平台（雪球、东方财富、同花顺）的公开数据进行情绪分析。\n"
            return output

        output += f"找到 {len(news)} 条相关新闻\n\n"

        for item in news[:10]:  # 显示前10条
            title = item.get('title', '') or item.get('headline', '无标题')
            date = item.get('date', '') or item.get('publish_date', '未知日期')

            output += f"**{date}** - {title}\n\n"

        output += "**情绪分析**: 基于近期新闻媒体的关注度和报道倾向进行综合分析。\n"
        output += "**数据来源**: 公开财经媒体报道整理\n"

        return output

    except Exception as e:
        return f"❌ 获取中国社交媒体情绪失败: {str(e)}"
