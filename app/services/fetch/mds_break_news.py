import requests
from typing import Any, Dict, List, Union
from datetime import datetime, timedelta

# ========================
# Constants
# ========================
# EQUITY_BREAKING_NEWS_URL = (
#     "https://uat-investments4.personal-banking.hsbc.com.hk/"
#     "api/wealth-mds-amh-pws-shp-api-hk-hbap-cert-proxy/v0/mds/hk/news/equity/breaking-news"
# )

EQUITY_BREAKING_NEWS_URL = (
    "http://mds-ex-equity-service.default.svc.cluster.local/wealth/api/v1/market-data/news/equity/breaking-news"
)

DEFAULT_HEADERS = {
    "X-HSBC-Chnl-CountryCode": "HK",
    "X-HSBC-Chnl-Group-Member": "HSBC",
    "X-HSBC-Locale": "en_US",
    "X-HSBC-Channel-Id": "MOBILE",
    "X-HSBC-App-Code": "STBPWS",
    "X-HSBC-Customer-Id": "STBPWS",
    "Content-Type": "application/json",
}

def fetch_equity_breaking_news_json(
    *,
    market: str = "HK",
    end_datetime: str | datetime | None = None,
    start_datetime: str | datetime | None = None,
    lookback_days: int = 7,
    records_per_page: int = 10,
    page: int = 1,
    timeout: int = 30,
    headers_override: dict | None = None,
    proxy_host: str = "uk-proxy-01.systems.uk.hsbc",
    proxy_port: int = 80,
) -> dict:
    """
    调用 equity breaking-news 接口获取数据，返回 resp.json()

    时间默认逻辑:
    - end_datetime 默认 = 当前时间（本地时区）
    - start_datetime 默认 = end_datetime - lookback_days（默认 7）

    时间格式输出:
    - YYYY-MM-DDTHH:MM:SS+08:00（不带微秒）
    """
    def _to_datetime(dt: str | datetime) -> datetime:
        if isinstance(dt, datetime):
            return dt
        return datetime.fromisoformat(dt)

    def _to_iso8601_seconds(dt: datetime) -> str:
        # 去掉微秒，避免出现 .727917
        return dt.replace(microsecond=0).isoformat()

    print('fetch_equity_breaking_news_json', '------------------------')
    end_dt = _to_datetime(end_datetime) if end_datetime is not None else datetime.now().astimezone()
    start_dt = _to_datetime(start_datetime) if start_datetime is not None else (end_dt - timedelta(days=lookback_days))

    headers = dict(DEFAULT_HEADERS)
    if headers_override:
        headers.update(headers_override)

    proxies = {
        "http": f"{proxy_host}:{proxy_port}",
        "https": f"{proxy_host}:{proxy_port}",
    }

    payload = {
        "market": market,
        "startDateTime": _to_iso8601_seconds(start_dt),
        "endDateTime": _to_iso8601_seconds(end_dt),
        "recordsperpage": str(records_per_page),
        "page": str(page),
    }

    resp = requests.post(
        EQUITY_BREAKING_NEWS_URL,
        headers=headers,
        json=payload,
        # proxies=proxies,
        timeout=timeout,
    )
    resp.raise_for_status()
    print('fetch_equity_breaking_news_json', 'ok')
    return resp.json()


def extract_newslist_as_str(
        data_json: Dict[str, Any],
        sep: str = "\n\n"
) -> str:
    """
    将 data_json['newslist'] 提取并拼接为指定的 str 格式。

    输出格式（每条）:
    newsTopic: ***
    newsDateTime ***
    prodAltNumList: []
    """
    newslist: List[Dict[str, Any]] = data_json.get("newslist", [])
    blocks: List[str] = []

    for item in newslist:
        topic = item.get("newsTopic", "")
        dt = item.get("newsDateTime", "")
        prod_list = item.get("prodAltNumList") or []  # None -> []

        blocks.append(
            f"newsTopic: {topic}\n"
            f"newsDateTime {dt}\n"
            f"prodAltNumList: {prod_list}"
        )

    return sep.join(blocks)


def extract_newslist_as_list(
        data_json: Dict[str, Any]
) -> List[str]:
    """
    返回逐条的字符串列表（每个元素是一条新闻的格式化文本）
    """
    text = extract_newslist_as_str(data_json, sep="\n\n")
    return text.split("\n\n") if text else []


def fetch_last_n_breaking_news(market: str = 'HK') -> str | None:
    """
    拉取新闻并渲染最后 n 条:
    - 成功: 返回渲染后的纯文本
    - 失败/无效: 返回 None

    market: 市场
        CN - China
        HK - Hong Kong
        US - United States
    """
    try:
        data = fetch_equity_breaking_news_json(
            market=market,
            records_per_page=10,
            page=1
        )
    except requests.RequestException as e:
        print('error 错误')
        print(e)
        return None

    data_str = extract_newslist_as_str(data)
    return data_str