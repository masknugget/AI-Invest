# 股票推荐系统 - 离线批处理架构

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      离线批处理层                            │
│  batch_generator.py - 每天运行一次                            │
│  ├─ 获取所有股票基础数据                                      │
│  ├─ 批量调用LLM生成推荐 (每批10只)                           │
│  ├─ 生成：评分/推荐等级/风险等级/适用风格/推荐理由             │
│  └─ 存储到 MongoDB (recommendations.daily_stock_recommendations)
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (每天凌晨运行，耗时约30-60分钟)
┌─────────────────────────────────────────────────────────────┐
│                      在线服务层                              │
│  recommendation_service.py - 实时响应用户请求                  │
│  ├─ 从MongoDB查询预计算的推荐数据                             │
│  ├─ 根据用户画像匹配 (风格/风险/行业)                         │
│  ├─ 本地排序，不调用LLM                                       │
│  └─ 毫秒级返回推荐结果                                        │
└─────────────────────────────────────────────────────────────┘
```

## 优势

| 对比项 | 实时LLM架构 | 离线批处理架构 |
|--------|-------------|----------------|
| 用户请求耗时 | 30-60秒 | <100毫秒 |
| LLM API调用 | 每次请求都调用 | 每天一次 |
| 成本 | 高 | 低 (节省99%+) |
| 可支持的并发 | 低 | 高 |
| 数据新鲜度 | 实时 | T+1 |

## 快速开始

### 1. 每日批处理（离线）

```bash
# 方式1: 直接运行脚本
python -m recommender.batch_generator

# 方式2: 使用便捷函数
python -c "from recommender import run_daily_batch; run_daily_batch()"

# 方式3: 只处理前100只（测试）
python -c "from recommender import run_daily_batch; run_daily_batch(max_stocks=100)"
```

### 2. 为用户推荐（在线）

```python
from recommender import RecommendationService, UserProfile

# 创建服务
service = RecommendationService()

# 创建用户画像
user = UserProfile(
    user_id="user_001",
    risk_level="中",                    # 低/中/高
    preferred_styles=["价值投资", "股息投资"],  # 偏好风格
    preferred_industries=["银行", "保险"],      # 偏好行业
    max_pe=20,                           # 最高PE
    min_dividend_yield=0.02              # 最低股息率2%
)

# 获取推荐（毫秒级响应）
recommendations = service.recommend(user, top_k=5)

for rec in recommendations:
    print(f"\n{rec.name} ({rec.symbol})")
    print(f"  匹配分数: {rec.score:.1f}")
    print(f"  推荐等级: {rec.recommendation}")
    print(f"  理由: {rec.reason}")
    print(f"  匹配原因: {rec.match_reason}")
    print(f"  标签: {', '.join(rec.tags)}")
```

### 3. 便捷函数

```python
from recommender import quick_recommend

recommendations = quick_recommend(
    user_id="user_001",
    risk_level="稳健型",
    preferred_styles=["价值投资"],
    preferred_industries=["银行"],
    top_k=5
)
```

## 用户画像参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `risk_level` | str | 风险承受力 | "低"/"中"/"高" |
| `preferred_styles` | List[str] | 偏好投资风格 | ["价值投资", "股息投资"] |
| `preferred_industries` | List[str] | 偏好行业 | ["银行", "保险"] |
| `max_pe` | float | 最高PE限制 | 20 |
| `min_dividend_yield` | float | 最低股息率 | 0.02 |

## 预计算数据结构

```python
StockRecommendation(
    symbol="000001",
    name="平安银行",
    industry="银行",
    pe=5.2,
    pb=0.6,
    roe=12.5,
    dividend_yield=0.04,
    overall_score=85,           # LLM生成的综合评分
    recommendation="买入",       # LLM生成的推荐等级
    risk_level="低",
    suitable_for=["价值投资", "股息投资"],  # LLM判断的适用风格
    reason_for_value="低估值，PE仅5倍",      # 价值投资理由
    reason_for_growth="成长性一般",          # 成长投资理由
    reason_for_dividend="股息率4%，稳定分红", # 股息投资理由
    analysis_date="2024-01-15"
)
```

## 匹配算法

```
最终匹配分数 = 
    预计算overall_score × 50% +
    投资风格匹配 × 30% +
    风险等级匹配 × 10% +
    行业偏好匹配 × 10%
```

## 定时任务设置

### Linux/Mac (crontab)

```bash
# 每天凌晨2点运行
0 2 * * * cd /path/to/project && python -m recommender.batch_generator >> /var/log/recommender.log 2>&1
```

### Windows (Task Scheduler)

创建任务计划，每天凌晨2点运行：
```
python.exe -m recommender.batch_generator
```

### 使用APScheduler（推荐）

```python
from apscheduler.schedulers.background import BackgroundScheduler
from recommender import run_daily_batch

scheduler = BackgroundScheduler()
scheduler.add_job(run_daily_batch, 'cron', hour=2, minute=0)
scheduler.start()
```

## 数据存储

- **数据库**: MongoDB
- **库名**: `recommendations`
- **集合**: `daily_stock_recommendations`
- **索引**: symbol, analysis_date, overall_score

## 文件结构

```
recommender/
├── __init__.py              # 模块导出
├── models.py                # 数据模型
├── batch_generator.py       # 离线批处理生成器
├── recommendation_service.py # 在线推荐服务
├── stock_scanner.py         # 股票数据遍历（保留）
└── README.md                # 本文档
```

## 注意事项

1. **首次运行**: 需要先运行批处理生成推荐数据，否则在线服务无数据返回
2. **数据更新**: 每天批处理完成后，在线服务自动使用新数据
3. **历史数据**: 可以查询历史日期的推荐（指定date参数）
4. **容错**: 如果某天批处理失败，在线服务会自动使用最近的有效数据
