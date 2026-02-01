import json
import random
from typing import Dict, Optional, Union
from datetime import datetime


_stock_data = {
    "000001": {"name": "平安银行", "price": 12.50},
    "600519": {"name": "贵州茅台", "price": 1680.00},
    "000858": {"name": "五粮液", "price": 156.80},
    "002415": {"name": "海康威视", "price": 32.60},
    "300750": {"name": "宁德时代", "price": 225.40},
    "平安银行": {"name": "平安银行", "price": 12.50, "code": "000001"},
    "贵州茅台": {"name": "贵州茅台", "price": 1680.00, "code": "600519"},
    "五粮液": {"name": "五粮液", "price": 156.80, "code": "000858"},
    "海康威视": {"name": "海康威视", "price": 32.60, "code": "002415"},
    "宁德时代": {"name": "宁德时代", "price": 225.40, "code": "300750"},
}


def search_stock_information(
    stock_code: str,
    date_time: Optional[str] = None,
    indicator_name: Optional[str] = None
) -> Dict[str, Union[str, float, None]]:
    """
    查找股票信息，搜索股票价格和技术指标
    
    Args:
        stock_code: 股票代码或名称
        date_time: 日期（格式：YYYY-MM-DD，默认为今天）
        indicator_name: 指标名称（如：收盘价、开盘价、成交量、涨跌幅等）
        
    Returns:
        股票信息字典，包含代码、名称、价格、指标等
    """
    stock_info = _stock_data.get(stock_code)
    
    if not stock_info:
        for code, info in _stock_data.items():
            if len(code) == 6 and stock_code in info["name"]:
                stock_info = info
                stock_code = code
                break
    
    if not stock_info:
        return {
            "success": False,
            "error": f"未找到股票: {stock_code}",
            "code": stock_code,
        }
    
    if date_time is None:
        date_time = datetime.now().strftime("%Y-%m-%d")
    
    indicator_value = None
    if indicator_name:
        indicator_name = indicator_name.replace("股价", "收盘价").replace("价格", "收盘价")
        
        if indicator_name in ["收盘价", "当前价", "价格"]:
            indicator_value = stock_info["price"]
        elif indicator_name == "开盘价":
            indicator_value = round(stock_info["price"] * random.uniform(0.98, 1.02), 2)
        elif indicator_name == "最高价":
            indicator_value = round(stock_info["price"] * random.uniform(1.01, 1.05), 2)
        elif indicator_name == "最低价":
            indicator_value = round(stock_info["price"] * random.uniform(0.95, 0.99), 2)
        elif indicator_name in ["成交量", "交易量"]:
            indicator_value = f"{random.randint(500000, 5000000):,}手"
        elif indicator_name == "涨跌幅":
            change = random.uniform(-3, 3)
            indicator_value = f"{change:+.2f}%"
        else:
            indicator_value = "数据暂不可用"
    
    return {
        "success": True,
        "code": stock_code,
        "name": stock_info["name"],
        "price": stock_info["price"],
        "indicator": indicator_name,
        "indicator_value": indicator_value,
        "date": date_time,
    }


def analyze_stock_information(stock_code: str) -> Dict[str, Union[str, float, None]]:
    """
    综合分析股票信息（基本面、技术面、新闻面）
    
    Args:
        stock_code: 股票代码或名称
        
    Returns:
        综合分析结果
    """
    stock_info = _stock_data.get(stock_code)
    
    if not stock_info:
        for code, info in _stock_data.items():
            if len(code) == 6 and stock_code in info["name"]:
                stock_info = info
                stock_code = code
                break
    
    if not stock_info:
        return {
            "success": False,
            "error": f"未找到股票: {stock_code}",
            "code": stock_code,
        }
    
    score = random.randint(60, 95)
    volatility = random.uniform(1, 5)
    pe_ratio = random.uniform(10, 50)
    recommendations = ["观望", "增持", "买入", "卖出", "持有"]
    
    analysis = f"""**{stock_info['name']}({stock_code})综合分析**

**技术面**：
- 当前价格：¥{stock_info['price']}
- 综合评分：{score}/100
- 波动率：{volatility:.2f}%
- 趋势：{'上涨' if random.random() > 0.4 else '震荡'}

**基本面**：
- 市盈率：{pe_ratio:.2f}
- 市值：{random.randint(500, 5000)}亿元
- 行业排名：{random.randint(1, 10)}/{random.randint(10, 30)}

**投资建议**：
- 短期：{random.choice(recommendations)}
- 中长期：{random.choice(recommendations)}
"""
    
    return {
        "success": True,
        "code": stock_code,
        "name": stock_info["name"],
        "price": stock_info["price"],
        "total_score": score,
        "analysis": analysis,
        "recommendation": analysis.split("短期：")[-1].split("\n")[0].strip() if "短期：" in analysis else "观望",
    }


def analyze_stock_by_type(stock_code: str, analyze_type: str) -> Dict[str, Union[str, float, None]]:
    """
    按指定类型分析股票（基本面、技术面、新闻面）
    
    Args:
        stock_code: 股票代码或名称
        analyze_type: 分析类型（基本面、技术面、新闻面）
        
    Returns:
        专项分析结果
    """
    stock_info = _stock_data.get(stock_code)
    
    if not stock_info:
        for code, info in _stock_data.items():
            if len(code) == 6 and stock_code in info["name"]:
                stock_info = info
                stock_code = code
                break
    
    if not stock_info:
        return {
            "success": False,
            "error": f"未找到股票: {stock_code}",
            "code": stock_code,
        }
    
    analyze_type = analyze_type.replace("面", "")
    
    if "基本面" in analyze_type or "价值" in analyze_type:
        pe_ratio = random.uniform(10, 50)
        pb_ratio = random.uniform(1, 5)
        roe = random.uniform(5, 30)
        
        content = f"""**{stock_info['name']}({stock_code})基本面分析**

**估值指标**：
- 市盈率(PE)：{pe_ratio:.2f}
- 市净率(PB)：{pb_ratio:.2f}
- 净资产收益率(ROE)：{roe:.1f}%

**财务健康**：
- 资产负债率：{random.uniform(30, 70):.1f}%
- 流动比率：{random.uniform(1.0, 3.0):.2f}

**行业对比**：
- 行业市盈率：{pe_ratio * random.uniform(0.8, 1.2):.2f}
- 相对估值：{'低估' if random.random() > 0.5 else '合理'}
"""
        
    elif "技术" in analyze_type or "图形" in analyze_type or "走势" in analyze_type:
        score = random.randint(60, 95)
        volatility = random.uniform(1, 5)
        
        content = f"""**{stock_info['name']}({stock_code})技术面分析**

**价格走势**：
- 当前价格：¥{stock_info['price']}
- 短期均线：{'多头' if random.random() > 0.5 else '空头'}排列
- 支撑/阻力：¥{stock_info['price'] * 0.95:.2f}/¥{stock_info['price'] * 1.05:.2f}

**技术指标**：
- 综合评分：{score}/100
- 波动率：{volatility:.2f}%
- MACD：{'金叉' if random.random() > 0.5 else '死叉'}
- RSI：{random.randint(30, 70)}
"""
        
    elif "新闻" in analyze_type or "消息" in analyze_type or "事件" in analyze_type:
        news_count = random.randint(3, 10)
        sentiment_score = random.randint(-50, 50)
        
        if sentiment_score > 20:
            sentiment = "偏多"
        elif sentiment_score < -20:
            sentiment = "偏空"
        else:
            sentiment = "中性"
        
        content = f"""**{stock_info['name']}({stock_code})新闻面分析**

**舆情概况**：
- 近期新闻：{news_count}条
- 市场情绪：{sentiment}（{sentiment_score:+d}分）
- 热点话题：{random.choice(['业绩预增', '行业政策', '技术创新', '战略合作'])}

**主要动态**：
1. 公司{random.choice(['发布新品', '签订大单', '获得认证', '高管变动'])}
2. 行业{random.choice(['政策利好', '竞争加剧', '技术突破', '需求增长'])}
3. 市场{random.choice(['机构关注', '资金流入', '评级上调', '调研频繁'])}
"""
        
    else:
        content = f"**{stock_info['name']}({stock_code})分析**\n\n未知分析类型\"{analyze_type}\"，请使用：基本面、技术面 或 新闻面。"
    
    return {
        "success": True,
        "code": stock_code,
        "name": stock_info["name"],
        "analysis_type": analyze_type,
        "content": content,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_all_tools():
    """获取所有工具函数"""
    return [
        search_stock_information,
        analyze_stock_information,
        analyze_stock_by_type,
    ]


def get_tools_json():
    """获取工具的JSON描述"""
    tools = get_all_tools()
    
    tool_schemas = []
    for tool in tools:
        schema = {
            "type": "function",
            "function": {
                "name": tool.__name__,
                "description": tool.__doc__.strip().split("\n")[0] if tool.__doc__ else "",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
        
        import inspect
        sig = inspect.signature(tool)
        params = schema["function"]["parameters"]
        
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            
            params["properties"][param_name] = {
                "type": param_type,
                "description": f"参数: {param_name}",
            }
            
            if param.default == inspect.Parameter.empty:
                params["required"].append(param_name)
        
        tool_schemas.append(schema)
    
    return json.dumps(tool_schemas, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print(get_tools_json())
