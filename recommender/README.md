# Recommender 股票遍历查询模块

## 概述

`stock_scanner.py` 提供了完整的股票信息遍历查询功能，支持 MongoDB 数据库的股票批量获取、筛选和处理。

## 快速开始

```python
from recommender.stock_scanner import (
    get_all_stocks,
    get_all_symbols,
    iterate_stocks,
    get_stocks_daily_data,
)

# 1. 获取所有A股
stocks = get_all_stocks(market='cn')

# 2. 遍历所有港股（分批处理，内存友好）
for batch in iterate_stocks(market='hk', batch_size=100):
    for stock in batch:
        print(f"{stock['symbol']}: {stock['name']}")

# 3. 批量获取历史数据
data = get_stocks_daily_data(
    symbols=['000001', '600000'],
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

## 核心功能

### 1. 股票列表获取

| 函数 | 用途 | 适用场景 |
|------|------|---------|
| `get_all_stocks()` | 获取完整股票信息列表 | 数据量不大时 |
| `get_all_symbols()` | 只获取股票代码 | 只需要代码列表 |
| `get_stock_count()` | 获取股票数量 | 统计用途 |

```python
# 获取所有A股基本信息
stocks = get_all_stocks(market='cn')

# 只获取代码（更轻量）
symbols = get_all_symbols(market='hk')

# 带筛选
stocks = get_all_stocks(
    market='cn',
    industry='银行',
    fields=['symbol', 'name', 'pe_ttm']
)
```

### 2. 分批遍历（推荐）

使用生成器分批遍历，避免内存溢出：

```python
# 方式1: 分批获取（每批返回列表）
for batch in iterate_stocks(market='cn', batch_size=100):
    # batch 是包含100只股票的列表
    process_batch(batch)

# 方式2: 逐个获取（游标方式，最省内存）
for stock in iterate_stocks_with_cursor(market='cn'):
    # stock 是单个股票信息
    process_stock(stock)
```

### 3. 批量历史数据获取

```python
# 获取多只股票的日线数据
symbols = ['000001', '000002', '600000']
data = get_stocks_daily_data(
    symbols=symbols,
    start_date='2024-01-01',
    end_date='2024-12-31',
    data_type='technical'  # 或 'basic'
)

# data 格式: {symbol: [daily_data_list]}
for symbol, daily_list in data.items():
    print(f"{symbol}: {len(daily_list)} 条记录")
```

### 4. 筛选与统计

```python
# 市场分布
distribution = get_market_distribution()
# {'cn': 5000, 'hk': 2500, 'us': 8000}

# 行业分布
industries = get_industries(market='cn')
# [{'industry': '银行', 'count': 42}, ...]

# 多条件筛选
stocks = filter_stocks(
    market='cn',
    industries=['银行', '保险'],
    min_market_cap=1000000000,  # 最小市值
    limit=100
)
```

### 5. 并发批量处理

```python
def analyze_stock(stock):
    """自定义处理函数"""
    symbol = stock['symbol']
    # 执行分析...
    return {'symbol': symbol, 'score': calculate_score(symbol)}

# 并发处理所有A股
results = batch_process_stocks(
    processor=analyze_stock,
    market='cn',
    batch_size=50,
    max_workers=4
)
```

## 市场标识说明

| 标识 | 市场 |
|------|------|
| `cn` | A股（上海、深圳） |
| `hk` | 港股（港交所） |
| `us` | 美股（纽交所、纳斯达克） |

## 推荐用法

### 场景1: 遍历所有股票计算指标

```python
from recommender.stock_scanner import iterate_stocks

results = []
for batch in iterate_stocks(market='cn', batch_size=100):
    for stock in batch:
        symbol = stock['symbol']
        # 计算指标...
        score = calculate_indicator(symbol)
        results.append({'symbol': symbol, 'score': score})
    
    # 每批处理完后保存进度
    save_progress(results)
```

### 场景2: 获取指定行业股票

```python
# 获取所有科技股
stocks = get_all_stocks(
    market='cn',
    industry='科技',
    fields=['symbol', 'name', 'industry', 'pe_ttm']
)
```

### 场景3: 多线程批量分析

```python
from concurrent.futures import ThreadPoolExecutor
from recommender.stock_scanner import get_all_symbols, get_stock_data

def analyze(symbol):
    data = get_stock_data(symbol, '2024-01-01', '2024-12-31')
    return {'symbol': symbol, 'trend': calculate_trend(data)}

symbols = get_all_symbols(market='cn')

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(analyze, symbols))
```

## 性能优化建议

1. **优先使用分批遍历** - `iterate_stocks()` 使用生成器，内存占用最小
2. **指定需要的字段** - 使用 `fields` 参数减少数据传输
3. **合理使用并发** - 对于网络IO密集型操作可使用 `batch_process_stocks`
4. **使用缓存** - 频繁查询的基础信息可使用 `get_stock_basic_cached()`

## 注意事项

- MongoDB 连接在每次查询后自动关闭，无需手动管理
- 大批量处理时建议使用 `iterate_stocks` 避免内存溢出
- 日期格式统一为 `YYYY-MM-DD`
