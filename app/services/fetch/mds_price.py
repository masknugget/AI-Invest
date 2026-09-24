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
    "http://mds-ex-equity-service.default.svc.cluster.local/wealth/api/v1/market-data/news/equity/charts/performance"
)

def fetch_equity_performance_json(
        symbol: str,
        *,
        market: str = "HK",
        product_type: str = "SEC",
        period: int = 1,
        int_cnt: int = 1,
        int_type: str = "MINUTE",
        filters=None,
        timeout: int = 10,
        headers_override: dict | None = None,
        proxy_host: str = "uk-proxy-01.systems.uk.hsbc",
        proxy_port: int = 80,
):
    """
    调用 performance 接口获取数据，返回 resp.json()

    - proxies 在函数内部组装
    - URL 使用外部常量 PERFORMANCE_URL
    - headers_override 用于覆盖/补充默认 headers
    """
    if filters is None:
        filters = ["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]

    headers = {
        "X-HSBC-Chnl-CountryCode": "HK",
        "X-HSBC-Chnl-Group-Member": "HSBC",
        "X-HSBC-Locale": "en_US",
        "X-HSBC-Channel-Id": "MOBILE",
        "X-HSBC-App-Code": "STBPWS",
        "X-HSBC-Customer-Id": "STBPWS",
        "Content-Type": "application/json",
    }
    if headers_override:
        headers.update(headers_override)

    proxies = {
        "http": f"{proxy_host}:{proxy_port}",
        "https": f"{proxy_host}:{proxy_port}",
    }

    payload = {
        "market": market,
        "productType": product_type,
        "symbol": [symbol],
        "period": period,
        "intCnt": int_cnt,
        "intType": int_type,
        "filters": filters,
    }

    resp = requests.post(
        PERFORMANCE_URL,
        headers=headers,
        json=payload,
        # proxies=proxies,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def extract_last_n_to_md(data_json, n=3, result_index=0):
    result0 = data_json["result"][result_index]
    fields = result0["fields"]
    data = result0["data"]

    last_n = data[-n:] if n > 0 else []
    structured = [fields] + last_n

    header_line = "| " + " | ".join(map(str, fields)) + " |"
    sep_line = "| " + " | ".join(["---"] * len(fields)) + " |"
    row_lines = ["| " + " | ".join(map(str, r)) + " |" for r in last_n]
    md_table = "\n".join([header_line, sep_line] + row_lines)

    return md_table


def check_mds_response_ok(data_json: dict) -> bool:
    """
    返回 True/False:
    - True: 结构正常且 result[0]['data'] 非空
    - False: 返回错误结构（含 reasonCode）或数据/结构不符合预期
    """
    # 明确的错误结构（如: {'traceCode','reasonCode','text'}）
    if isinstance(data_json, dict) and "reasonCode" in data_json:
        return False

    # 基本结构校验
    if not isinstance(data_json, dict):
        return False

    result = data_json.get("result")
    if not isinstance(result, list) or not result:
        return False

    first = result[0]
    if not isinstance(first, dict):
        return False

    fields = first.get("fields")
    data = first.get("data")

    if not isinstance(fields, list) or not fields:
        return False

    if not isinstance(data, list) or not data:
        return False

    return True


def fetch_last_price_by_code(code: str, n: int = 3) -> str | None:
    """
    只传入股票 code（symbol），内部完成:
    - 拉取 data_json
    - 校验返回是否OK
    - 提取最后 n 条并生成 Markdown 表格

    返回:
    - 成功: Markdown 表格字符串
    - 失败: None
    """
    try:
        data_json = fetch_equity_performance_json(code)

        if not check_mds_response_ok(data_json):
            return None

        md_table = extract_last_n_to_md(data_json, n=n)
        return md_table

    except requests.exceptions.RequestException:
        # 网络/超时/HTTP错误等
        return None
    except (KeyError, TypeError, ValueError):
        # 数据结构不符合预期等
        return None