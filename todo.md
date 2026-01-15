tradingagent是和app怎么通信的


mongodb

stock_basic_info

```commandline
{
  "_id": {
    "$oid": "6943fbd4d9fb219fe4888837"
  },
  "code": "000001",
  "source": "akshare",
  "area": "",
  "category": "stock_cn",
  "full_symbol": "000001.SZ",
  "industry": "",
  "list_date": "",
  "market": "主板",
  "name": "平安银行",
  "sse": "深圳证券交易所",
  "symbol": "000001",
  "total_mv": 2225.8588173106,
  "updated_at": {
    "$date": "2026-01-13T14:38:03.781Z"
  }
}

```
stock_daily_quotes
```commandline
{
  "_id": {
    "$oid": "695a6e1380ee33a6f4330aba"
  },
  "symbol": "000001",
  "code": "000001",
  "full_symbol": "000001.SZ",
  "market": "CN",
  "trade_date": "2025-11-05",
  "period": "daily",
  "data_source": "akshare",
  "created_at": {
    "$date": "2026-01-04T13:41:39.305Z"
  },
  "updated_at": {
    "$date": "2026-01-04T13:41:39.305Z"
  },
  "version": 1,
  "open": 11.59,
  "high": 11.6,
  "low": 11.5,
  "close": 11.52,
  "pre_close": null,
  "volume": 794926,
  "amount": 918112474.29,
  "change": -0.07,
  "pct_chg": -0.6
}

```

stock_screening_view

```commandline
{
  "_id": {
    "$oid": "6943fbd4d9fb219fe4888837"
  },
  "code": "000001",
  "source": "akshare",
  "area": "",
  "industry": "",
  "list_date": "",
  "market": "主板",
  "name": "平安银行",
  "total_mv": 2225.8588173106,
  "updated_at": {
    "$date": "2026-01-13T14:38:03.781Z"
  },
  "close": 11.49,
  "open": 11.48,
  "high": 11.54,
  "low": 11.46,
  "pre_close": 11.48,
  "pct_chg": 0.087,
  "amount": 959630350,
  "volume": 83457220,
  "trade_date": "20260112",
  "quote_updated_at": {
    "$date": "2026-01-13T06:04:13.347Z"
  }
}
```