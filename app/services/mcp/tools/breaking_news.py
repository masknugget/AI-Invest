from app.services.fetch.mds_break_news import fetch_last_n_breaking_news


def get_breaking_news(market: str = 'HK'):
    """
    宏观新闻查找：用于按市场维度检索"突发/快讯"类新闻，并返回格式化后的文本结果。

    参数
    ----
    market : str, default 'HK'
        市场标识（支持多种别名输入）。函数会先做标准化处理（去首尾空格 + 转大写），
        然后将别名映射为统一的三种标准市场代码:
        - CN: A股/中国（例: 'A股'、'沪深'、'SH'、'SZ'、'China' 等）
        - HK: 港股/香港（例: '港股'、'HKEX'、'Hong Kong' 等）
        - US: 美股/美国（例: '美股'、'NYSE'、'NASDAQ'、'USA' 等）

        若传入值不在别名列表中，将保留传入值（标准化后的原值）继续调用下游数据源。

    返回
    ----
    str
        格式化后的文本；
        - 成功: 包含"找到的内容如下:"与新闻内容
        - 失败: 异常时返回"找到的内容如下:"后为空字符串（不抛出异常）

    依赖
    ----
    fetch_last_n_breaking_news(market: str)
        下游函数: 根据标准市场代码拉取最近 N 条突发新闻内容。
    """
    # 输入标准化：避免大小写/空格导致映射失败
    market = (market or "").strip().upper()

    # 别名映射：将多种常见写法归一到标准市场代码 (CN/HK/US)
    if market in ("CN", "CHINA", "A股", "A股市场", "沪深", "沪深股市", "沪市", "深市", "SH", "SZ"):
        market = "CN"
    elif market in ("HK", "HONG KONG", "港股", "港股市场", "HKEX"):
        market = "HK"
    elif market in ("US", "USA", "UNITED STATES", "美股", "美股市场", "NYSE", "NASDAQ"):
        market = "US"
    else:
        # 未命中别名：保留标准化后的原输入（如 'JP'、'SG' 等），交由下游函数处理
        market = market

    # 拉取快讯：失败时兜底为空内容，保证函数稳定返回字符串
    try:
        content = fetch_last_n_breaking_news(market)
    except Exception:
        content = ""

    out_data = f"""
{content}
"""
    return out_data