# 组合压力测试原理说明（Portfolio Stress Test）

> 适用范围：`recommender/portfolio_advisor/stress_portfolio/` 计算引擎
> 及对外 MCP 工具 `app/services/mcp/tools/portfolio_advice/stress_test.py`（`portfolio_stress_test`）。
>
> 核心特征：**纯规则计算，零 LLM 调用**。引擎只输出结构化损失指标，情景解读文本由上层 AI 或前端生成。

---

## 一、什么是压力测试

压力测试回答一个问题：**如果发生某种极端行情，我的组合大概会亏多少？**

它不是预测，而是"假想敌"——把组合放到一组设定好的坏情形里，量测脆弱度。本项目实现了**三类相互独立**的压力情景，覆盖不同数据来源与假设强度：

| 类型 | `scenario_type` | 一句话原理 | 是否依赖真实行情 | 是否依赖行业映射 |
|------|-----------------|------------|:---:|:---:|
| 历史极端行情 | `history` | 用真实历史跌幅重演：组合损失 = Σ(权重 × 各票在该区间的最大回撤) | ✅ 需要 | ❌ 不需要 |
| 宏观情景冲击 | `scenario` | 假设某宏观事件对各板块打出不同冲击：组合损失 = Σ(权重 × 板块冲击) | ❌ 不需要 | ✅ 需要 |
| 行业板块回调 | `sector` | 假设单一板块整体回调：命中板块的票按 Beta 放大，其余为 0 | ❌ 不需要 | ✅ 需要 |

三类结果都以**百分比**呈现，符号约定统一为：**负数表示亏损**（如 `-12.0` 表示亏 12%）。

---

## 二、整体数据流

```
前端 / MCP 调用
   portfolio_stress_test(codes, weights, scenario_type, scenario_names)
        │
        ├── _common.validate_portfolio()      # 去重/校验/权重归一化到和为 1
        ├── _common.build_portfolio_arg()     # → [{"code":..., "weight":...}, ...]
        │
        └── 按 scenario_type 分发到三个引擎函数（dispatch 表）
             │
             ├─ history  → data_source.fetch_quotes(codes)   # 拉真实行情 DataFrame
             │             → compute_historical_stress(portfolio, dfs_map)
             │
             ├─ scenario → compute_scenario_stress(portfolio, name, industry_lookup)
             │
             └─ sector   → compute_sector_stress(portfolio, sector, industry_lookup)
        │
        └── 统一响应封装 make_response({status, tool, data, warnings, error})
```

单个情景计算失败（如某宏观情景名不认识）不会中断整体流程，失败信息写进 `warnings`，其余情景照常返回——这是"优雅降级"设计。

关键的两条外部依赖：
- **行情**：`history` 类型靠 `data_source.fetch_quotes`，多源冗余（MongoDB `stock_daily_quotes` 兜底 → akshare → yfinance）。
- **行业**：`scenario` / `sector` 靠 `data_source.industry_lookup(code)`，把股票代码映射到"申万一级行业名称"（如 `银行`、`电子`）。

---

## 三、核心概念：行业 → 板块桶 → 冲击

`scenario` 与 `sector` 两类都建立在一条"三级映射链"上（定义在 `stress_portfolio/const.py`）：

```
股票代码 --industry_lookup--> 申万一级行业 --SW_INDUSTRY_TO_SECTOR--> 板块桶 --映射--> 冲击/Beta
 (sz.000001)                  (银行)                                (金融)         (见下表)
```

**板块桶**共 5 个：`科技 / 医药 / 金融 / 消费 / 周期`。`SW_INDUSTRY_TO_SECTOR` 把 31 个申万一级行业归到这 5 桶，例如：

- 电子、计算机、通信、传媒 → **科技**
- 银行、非银金融 → **金融**
- 医药生物 → **医药**
- 食品饮料、家用电器、农林牧渔… → **消费**
- 化工、钢铁、房地产、汽车、国防军工… → **周期**

各板块桶的 **Beta**（对大盘的敏感度，用于 sector 类型）：

| 板块桶 | Beta |
|--------|------|
| 科技 | 1.15 |
| 医药 | 0.95 |
| 金融 | 0.85 |
| 消费 | 0.90 |
| 周期 | 1.05 |

> ⚠️ 若 `industry_lookup` 返回 `None`（查不到行业），该票的 `sector_bucket` 为 `NaN`，冲击经 `.fillna(0.0)` 后**被静默记为 0**，导致组合损失算成 `0.00%`。这不是"没有风险敞口"，而是"无法测算"。详见第五节的已知坑。

---

## 四、三类情景的计算原理与举例

### 4.1 历史极端行情（history）

**原理**：真实发生过。取每只票在指定历史区间内的**最大回撤（MDD）**，按权重加权得到组合损失。

**单票最大回撤公式**（`calculate_historical_drawdown`）：

```
peak(t) = 截至 t 日的历史最高收盘价（cummax）
drawdown(t) = (close(t) - peak(t)) / peak(t)
max_drawdown = min(drawdown)      # 区间内最深的一坑
```

**组合损失**（`calculate_historical_scenario_result`）：

```
组合损失% = Σ ( weight_i × max_drawdown_i ) × 100
```

**预定义历史区间**（`const.EXTREME_SCENARIOS`）：

| 场景 | 区间 | 基准回撤（沪深300） |
|------|------|------|
| 2021-2022年核心资产泡沫破裂 | 2021-02-10 ~ 2022-10-31 | -41.0% |
| 2024年5-9月阴跌磨底 | 2024-05-20 ~ 2024-09-18 | -14.4% |
| 2025年4月关税冲击 | 2025-03-19 ~ 2025-04-07 | -10.5% |

**举例**：
设组合 `TEST_A` 权重 100%，价格从 100 涨到 120 再跌到 80。
- 峰值 120，谷底 80 → `max_drawdown = (80-120)/120 = -0.3333` → -33.33%
- 组合损失 = `1.0 × (-33.33%) = -33.33%`

再设一个两票组合（各 50%），A 回撤 -30%、B 回撤 -20%：
- 组合损失 = `0.5 × (-30%) + 0.5 × (-20%) = -25.0%`

**数据覆盖度 `data_coverage`**：如果某些票在该历史区间内没有行情数据（例如当时还没上市），其回撤被记 0，`data_coverage` 会小于 1，提示"实际损失可能被低估"。例：A(60%)有数据、B(40%)缺数据 → `data_coverage = 0.6`。

---

### 4.2 宏观情景冲击（scenario）

**原理**：假设某宏观事件（加息/通胀/衰退）对**多个板块同时**打出不同方向和幅度的冲击。不依赖行情，只依赖行业映射。

**预定义情景冲击表**（`scenario_stress.DEFAULT_SCENARIO_SHOCKS`）：

| 板块 \ 情景 | 美联储加息 | 通胀上行 | 经济衰退 |
|------------|:---:|:---:|:---:|
| 科技 | -0.15 | -0.10 | -0.20 |
| 医药 | -0.05 | -0.02 | -0.03 |
| 金融 | **+0.03** | **+0.05** | -0.15 |
| 消费 | -0.08 | -0.06 | -0.12 |
| 周期 | -0.10 | **+0.08** | -0.18 |

（正数代表该板块在此情景下反而受益，如加息利好银行息差。）

**组合损失**（`calculate_scenario_stress_result`）：

```
每票压力收益 = scenario_shocks[ 板块桶(行业(代码)) ]     # 查不到则 0
组合损失% = Σ ( weight_i × 压力收益_i ) × 100
```

**举例（加息）**：组合为 科技 40% / 金融 30% / 消费 30%，跑「美联储加息」：
```
组合损失 = 0.4×(-0.15) + 0.3×(+0.03) + 0.3×(-0.08)
         = -0.060     + 0.009        + -0.024
         = -0.075  →  -7.5%
```
科技是主要拖累，金融反而小幅对冲。

**举例（经济衰退）**：同样组合跑「经济衰退」：
```
= 0.4×(-0.20) + 0.3×(-0.15) + 0.3×(-0.12)
= -0.080      + -0.045      + -0.036
= -0.161  →  -16.1%
```
衰退是全板块利空，损失显著大于加息。

---

### 4.3 行业板块回调（sector）

**原理**：只打击**单一板块**，命中该板块的股票按其 Beta 放大回调幅度，其余股票不受影响。

**公式**（`calculate_sector_stress_result`）：
```
命中板块的票：压力收益 = - 板块回调幅度 × 该板块 Beta
未命中的票：  压力收益 = 0
组合损失% = Σ ( weight_i × 压力收益_i ) × 100
```
默认回调幅度 `DEFAULT_SECTOR_CALLBACK_PCT = 0.20`（即 20%）。

**举例（科技板块回调 20%）**：组合为 电子(科技) 50% + 银行(金融) 50%：
```
Beta(科技) = 1.15
电子压力收益 = -0.20 × 1.15 = -0.23   → 命中
银行压力收益 = 0                    → 未命中（不是科技）
组合损失 = 0.5 × (-0.23) + 0.5 × 0 = -0.115  → -11.5%
```

若换成「金融板块回调 20%」，则命中变银行、Beta=0.85：
```
银行压力收益 = -0.20 × 0.85 = -0.17
组合损失 = 0.5 × 0 + 0.5 × (-0.17) = -0.085 → -8.5%
```

---

## 五、调用方式

### 5.1 MCP 工具（对外）

```python
from app.services.mcp.tools.portfolio_advice import stress_test
import json

resp = json.loads(stress_test.portfolio_stress_test(
    codes=["sz.000001", "sz.000002"],
    weights=[0.5, 0.5],
    scenario_type="scenario",        # history / scenario / sector
    scenario_names=None,             # None = 该类型下全部情景；也可指定 ["美联储加息"]
))
print(resp["status"], resp["warnings"])
for r in resp["data"]["results"]:
    print(r["scenario_name"], r["portfolio_loss_pct"], "%")
```

返回统一 JSON 结构 `{status, tool, data, warnings, error}`，其中 `data.results` 是各情景损失字典列表。

> 技巧：可先以 `scenario_names=[]` 空列表调用一次，从返回的 `warnings` 里拿到该类型下的全部可用情景名。

### 5.2 引擎函数（内部/测试）

```python
from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
    compute_scenario_stress,
)

portfolio = [
    {"code": "A", "weight": 0.4, "amount": 40000},
    {"code": "B", "weight": 0.6, "amount": 60000},
]
result = compute_scenario_stress(
    portfolio,
    "美联储加息",
    industry_lookup=lambda c: "电子" if c == "A" else "银行",
)
# result: {scenario_name, portfolio_loss_pct, portfolio_loss_amount,
#          per_asset, affected_stocks, warnings}
```

### 5.3 用法示例脚本

`tests/test_services/test_mcp/portfolio/run_stress_test.py` 依次演示 `scenario / sector / history` 三类真实调用并打印结果：

```powershell
F:\project_work\hf\AI-Invest\.venv\Scripts\python.exe `
  tests/test_services/test_mcp/portfolio/run_stress_test.py
```

---

## 六、输出字段含义

各情景返回字典的关键字段：

| 字段 | 含义 |
|------|------|
| `scenario_name` / `scenario` | 情景名称 |
| `portfolio_loss_pct` | 组合损失百分比（负=亏损）。history 保留 1 位小数，scenario/sector 保留 2 位 |
| `portfolio_loss_amount` | 组合损失金额（需 `amount` 字段，缺省时以权重近似） |
| `per_asset` | 逐票明细：权重、行业/板块桶、压力收益、单票损失金额 |
| `affected_stocks` | 实际受到冲击（压力收益≠0 或命中板块）的标的列表 |
| `data_coverage` | （仅 history）有区间行情数据的权重占比，<1 表示损失可能被低估 |
| `benchmark_drawdown` | （仅 history）该区间基准指数回撤，便于对比 |
| `warnings` | 数据缺失、代码不识别等提示 |

---

## 七、已知坑与注意事项

1. **行业查不到 → 静默变 0（最常见的"没有数据"）**
   `industry_lookup` 目前走 `tradingagents.db.document.get_stock_info`，硬编码查 `stock_db.stock_daily_basic`，而主库实为 `tradingagentscn`、行业字段常在 `stock_basic_info`。库/集合/symbol 格式任一不匹配都会让全部持仓落入"未知行业"，`scenario`、`sector` 损失算成 `0.00%`，`affected_stocks=0`。**同一次全景报告里"行业分布"也会是未知**，可据此交叉定位。
   判据：结果 0.00% 且告警含"无法识别行业"→ 是"无法测算"，不是"无敞口"。

2. **`scenario` / `sector` 不需要行情，`history` 需要行情**
   若只有 `history` 缺数据而另两类正常，说明是行情源问题；反之若两类为 0、history 正常，则问题在行业映射。

3. **权重必须归一化**
   引擎校验"权重之和 == 1"（`_validate_portfolio` / `_ensure_portfolio_df`）。MCP 层 `validate_portfolio` 会自动归一化，直接调引擎函数需自行保证。

4. **符号约定**
   所有损失百分比统一"负数=亏损"，前端展示时取绝对值并配红色/"↓"。

5. **Beta 为简化静态值**
   `SECTOR_BETAS` 是硬编码的经验值，非实时回归；设计文档设想后续可替换为回归计算。

6. **宏观情景为人工假设值**
   `DEFAULT_SCENARIO_SHOCKS` 里的板块冲击是拍的先验常数，不代表任何真实模型输出，解读时应说明"假设"性质。

---

## 八、模块文件索引

| 文件 | 职责 |
|------|------|
| `stress_portfolio/const.py` | 历史区间库、行业→板块桶映射、板块 Beta、场景数据类与工厂 |
| `stress_portfolio/history_stress.py` | 历史极端行情：最大回撤 + 加权损失 + 净值/回撤时间序列模拟 |
| `stress_portfolio/scenario_stress.py` | 宏观情景：多板块组合冲击 |
| `stress_portfolio/sector_stress.py` | 行业板块：单板块回调 × Beta |
| `app/services/mcp/tools/portfolio_advice/stress_test.py` | 对外 MCP 工具，按类型分发 + 统一响应 |
| `app/services/mcp/tools/portfolio_advice/data_source.py` | 行情多源获取 + `industry_lookup` 行业查询 |
| `app/services/mcp/tools/portfolio_advice/full_report.py` | 全景报告：三类压力测试 + 五维评分 + 风险指标汇总 |
