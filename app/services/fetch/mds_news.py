"""
- render_last_n_news_text(): 取最后 n 条新闻，输出可直接 print 的纯文本
"""

from __future__ import annotations

from datetime import datetime
import re
import requests

# ========================
# Constants
# ========================
# EQUITY_HEADLINES_URL = (
#     "https://uat-investments4.personal-banking.hsbc.com.hk/"
#     "api/wealth-mds-amh-pws-shp-api-hk-hbap-cert-proxy/v0/mds/hk/news/equity/headlines"
# )
EQUITY_HEADLINES_URL = (
    "http://mds-ex-equity-service.default.svc.cluster.local/wealth/api/v1/market-data/news/equity/headlines"
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

# ========================
# API
# ========================
def fetch_equity_headlines_json(
        symbol: str,
        *,
        market: str = "HK",
        product_code_indicator: str = "N",
        category: str = "NS",
        records_per_page: int = 10,
        page_id: int = 1,
        timeout: int = 10,
        headers_override: dict | None = None,
        proxy_host: str = "uk-proxy-01.systems.uk.hsbc",
        proxy_port: int = 80,
) -> dict:
    """
    调用 equity headlines 接口获取数据，返回 resp.json()

    参数要点:
    - headers_override: 覆盖/补充默认 headers
    - proxy_host/proxy_port: 函数内组装 proxies
    """
    headers = dict(DEFAULT_HEADERS)
    if headers_override:
        headers.update(headers_override)

    proxies = {
        "http": f"{proxy_host}:{proxy_port}",
        "https": f"{proxy_host}:{proxy_port}",
    }

    payload = {
        "market": market,
        "symbol": [symbol],
        "productCodeIndicator": product_code_indicator,
        "category": category,
        "recordsPerPage": records_per_page,
        "pageId": page_id,
    }

    resp = requests.post(
        EQUITY_HEADLINES_URL,
        headers=headers,
        json=payload,
        # proxies=proxies,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ========================
# Text helpers
# ========================
_BR_RE = re.compile(r"<br\s*/?>", flags=re.I)
_P_END_RE = re.compile(r"</p\s*>", flags=re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_MANY_NL_RE = re.compile(r"\n{3,}")


def strip_html(html: str) -> str:
    """把 brief 里的常见 HTML 标签清成纯文本。"""
    if not html:
        return ""
    text = _BR_RE.sub("\n", html)
    text = _P_END_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    return _MANY_NL_RE.sub("\n\n", text).strip()


def format_iso_datetime(iso_dt: str) -> str:
    """将 2026-08-17T10:55:20.000+08:00 格式化为 2026-08-17 10:55:20。"""
    if not iso_dt:
        return ""
    dt = datetime.fromisoformat(iso_dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def render_last_n_news_text(data_json: dict, n: int = 3) -> str:
    """
    取 newsList 最后 n 条，输出纯文本块，适合直接 print / 写入日志。
    """
    news_list = data_json.get("newsList") or []
    if not isinstance(news_list, list) or n <= 0:
        return ""

    items = news_list[-n:]  # 不足 n 条则全取
    blocks: list[str] = []

    for it in items:
        as_of = format_iso_datetime(it.get("asOfDateTime", ""))
        headline = (it.get("headline") or "").strip()
        brief = strip_html(it.get("brief", ""))

        blocks.append(
            f"asOfDateTime: {as_of}\n"
            f"headline: {headline}\n"
            f"brief: {brief}"
        )

    return "\n\n---\n\n".join(blocks)


def is_valid_headlines_response(data_json: object) -> bool:
    # 必须是 dict
    if not isinstance(data_json, dict):
        return False

    # MDS 错误返回通常包含 reasonCode/text（以及 traceCode）
    if "reasonCode" in data_json and "text" in data_json:
        return False

    # 正常返回应包含 newsList 且为 list
    return isinstance(data_json.get("newsList"), list)


def fetch_last_n_news(symbol: str, *, n: int = 3) -> str | None:
    """
    拉取新闻并渲染最后 n 条:
    - 成功: 返回渲染后的纯文本
    - 失败/无效: 返回 None
    """
    try:
        data = fetch_equity_headlines_json(symbol)
    except requests.RequestException:
        return None

    if not is_valid_headlines_response(data):
        return None

    return render_last_n_news_text(data, n=n)


# ========================
# Example usage