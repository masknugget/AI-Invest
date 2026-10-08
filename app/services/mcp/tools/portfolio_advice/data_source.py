"""
Portfolio Advisor MCP 工具 —— 数据获取层。

职责：
- 股票代码格式候选与市场探测（多格式冗余：sh.600000 / 600000 / 600000.SH ...）
- 行情 DataFrame 获取（多源冗余：MongoDB -> akshare(A股) -> yfinance(港美股)）
- 行业查询与行业分布聚合

所有函数返回引擎所需的标准结构（date/code/close/pctChg DataFrame），
不处理响应封装与参数校验（见 _common.py）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

# 行情回看年限
QUOTE_LOOKBACK_YEARS = 3


# ============================================================================
# 股票代码格式候选（多格式冗余探测）
# ============================================================================

def _symbol_candidates(code: str) -> List[str]:
    """根据 baostock 风格代码（sh.600000 / sz.000001 / hk.00700）生成各数据源可能使用的格式。"""
    c = code.strip()
    candidates: List[str] = [c]
    if "." in c:
        market, num = c.split(".", 1)
        market = market.lower()
        if market in ("sh", "sz", "bj"):
            candidates += [num, f"{market}{num}", f"{num}.SH", f"{num}.SZ", f"{num}.BJ"]
        elif market == "hk":
            candidates += [num, f"{num}.HK", f"{num.zfill(5)}.HK"]
        else:  # us 等
            candidates += [num.upper(), f"{num.upper()}.US"]
    else:
        candidates += [c.upper()]
    # 保序去重
    seen: set = set()
    result = []
    for x in candidates:
        if x and x not in seen:
            seen.add(x)
            result.append(x)
    return result


def detect_code_market(code: str) -> str:
    """粗略识别市场：cn / hk / us / unknown。"""
    try:
        from tradingagents.db.document import detect_market

        for sym in _symbol_candidates(code):
            m = detect_market(sym)
            if m != "unknown":
                return m
        return "unknown"
    except Exception:
        pass
    c = code.strip().lower()
    if c.startswith(("sh.", "sz.", "bj.")):
        return "cn"
    if c.startswith("hk."):
        return "hk"
    return "unknown"


# ============================================================================
# 行情数据获取（多源冗余：MongoDB -> akshare(CN) -> yfinance(HK/US)）
# ============================================================================

_QUOTE_FIELD_ALIASES = {
    "date": ["trade_date", "date", "日期", "Date"],
    "close": ["close", "收盘", "Close", "adj_close", "Adj Close"],
    "pctChg": ["pctChg", "pct_chg", "changepercent", "涨跌幅", "PctChg"],
    "code": ["symbol", "code", "股票代码"],
}


def _pick_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    for name in aliases:
        if name in df.columns:
            return name
    return None


def _records_to_df(records: List[Dict[str, Any]], code: str) -> Optional[pd.DataFrame]:
    """将 MongoDB / akshare / yfinance 记录统一转换为引擎所需的 date/code/close/pctChg DataFrame。"""
    if not records:
        return None
    df = pd.DataFrame(records)
    date_col = _pick_column(df, _QUOTE_FIELD_ALIASES["date"])
    close_col = _pick_column(df, _QUOTE_FIELD_ALIASES["close"])
    if not date_col or not close_col:
        return None
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
            "code": code,
            "close": pd.to_numeric(df[close_col], errors="coerce"),
        }
    )
    pct_col = _pick_column(df, _QUOTE_FIELD_ALIASES["pctChg"])
    if pct_col:
        # akshare 风格的 pctChg 为百分数数值，统一除以 100
        raw = pd.to_numeric(df[pct_col], errors="coerce")
        out["pctChg"] = raw / 100.0 if raw.abs().median() > 1.5 else raw
    else:
        out["pctChg"] = out["close"].pct_change()
    out = out.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(out) < 2:
        return None
    return out


def _fetch_quote_from_db(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    try:
        from tradingagents.db.document import get_stock_data
    except Exception:
        return None
    for sym in _symbol_candidates(code):
        try:
            records = get_stock_data(sym, start_date, end_date, "technical")
        except Exception:
            continue
        df = _records_to_df(records, code)
        if df is not None:
            return df
    return None


def _fetch_quote_from_akshare(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    if detect_code_market(code) != "cn":
        return None
    num = code.split(".", 1)[1] if "." in code else code
    try:
        import akshare as ak

        df = ak.stock_zh_a_hist(
            symbol=num, period="daily", start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""), adjust="qfq",
        )
    except Exception:
        return None
    return _records_to_df(df.to_dict(orient="records"), code)


def _fetch_quote_from_yfinance(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    if detect_code_market(code) == "cn":
        return None
    candidates = [s for s in _symbol_candidates(code) if s.endswith(".HK") or "." not in s]
    try:
        import yfinance as yf
    except Exception:
        return None
    for sym in candidates:
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        df = df.reset_index()
        records = df.to_dict(orient="records")
        out = _records_to_df(records, code)
        if out is not None:
            return out
    return None


def fetch_quote_df(code: str, lookback_years: int = QUOTE_LOOKBACK_YEARS) -> pd.DataFrame:
    """
    获取单只标的历史行情 DataFrame（date/code/close/pctChg 列）。

    多源冗余：MongoDB(tradingagents.db.document) -> akshare(A股) -> yfinance(港美股)。
    全部失败时抛 ValueError（中文信息）。
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365 * lookback_years)).strftime("%Y-%m-%d")

    df = _fetch_quote_from_db(code, start_date, end_date)
    if df is not None:
        return df
    df = _fetch_quote_from_akshare(code, start_date, end_date)
    if df is not None:
        return df
    df = _fetch_quote_from_yfinance(code, start_date, end_date)
    if df is not None:
        return df
    raise ValueError(
        f"无法获取 {code} 的历史行情（已尝试 MongoDB / akshare / yfinance），"
        "请确认数据已入库或网络可用"
    )


def fetch_quotes(codes: List[str]) -> Dict[str, pd.DataFrame]:
    """批量获取行情，任一失败即抛错（附带已成功/失败明细）。"""
    dfs: Dict[str, pd.DataFrame] = {}
    failed: List[str] = []
    for code in codes:
        try:
            dfs[code] = fetch_quote_df(code)
        except Exception:
            failed.append(code)
    if failed:
        ok = [c for c in codes if c not in failed]
        raise ValueError(f"以下标的行情获取失败: {failed}（成功: {ok}）")
    return dfs


# ============================================================================
# 行业查询（MongoDB 冗余，失败归入未知）
# ============================================================================

def industry_lookup(code: str) -> Optional[str]:
    """查询股票所属行业；失败返回 None（由调用方归入未知行业）。"""
    try:
        from tradingagents.db.document import get_stock_info
    except Exception:
        return None
    for sym in _symbol_candidates(code):
        try:
            info = get_stock_info(sym)
        except Exception:
            continue
        if info and info.get("industry"):
            return info["industry"]
    return None


def build_industry_distribution(codes: List[str], weights: List[float]) -> Dict[str, float]:
    """按权重聚合一级行业分布，查询不到归入 未知行业。"""
    dist: Dict[str, float] = {}
    for code, w in zip(codes, weights):
        industry = industry_lookup(code) or "未知行业"
        dist[industry] = dist.get(industry, 0.0) + w
    return dist
