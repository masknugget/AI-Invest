| 模块          | 功能描述                                   | 优先级 |
| ----------- | -------------------------------------- | --- |
| **综合健康度评分** | 基于多维度算法生成账户健康分数（0-100），并给出评级标签         | P0  |
| **五维能力透视**  | 通过雷达图可视化展示收益稳定性、风格均衡、持仓性价比、抗回撤能力、资产分散度 | P0  |
| **核心风险提示**  | 智能识别持仓风险（行业集中度、波动率等），以卡片形式呈现风险详情与影响说明  | P0  |
| **行业分布地图**  | 以进度条形式展示各行业持仓占比，支持直观对比                 | P1  |
| **AI优化方案**  | 提供"查看AI优化方案"入口，引导用户进入调仓建议页面            | P1  |
| **分享功能**    | 右上角分享按钮，支持生成诊断报告图片或链接分享                | P2  |




---

| 维度    | 目测得分 | 权重  | 加权得分  | 截图线索           |
| ----- | ---- | --- | ----- | -------------- |
| 收益稳定性 | 90   | 25% | 22.50 | "持仓收益稳健"       |
| 持仓性价比 | 80   | 20% | 16.00 | —              |
| 风格均衡  | 75   | 15% | 11.25 | —              |
| 抗回撤能力 | 65   | 20% | 13.00 | 行业集中导致波动剧烈     |
| 资产分散度 | 50   | 20% | 10.00 | "行业集中度偏高"（42%） |


---


# 投资的个数

我希望的映射到0-100的分数

组合至少有1个

当是1的时候呢


只能是，每一个都有分析维度，然后组合是加权评价


drawdown_control:
    最大回撤 Maximum Drawdown (MDD)

    投资组合的最大回撤

portfolio_diversification:
    有效下注数 (Effective Number of Bets, ENB)

position_efficiency:
    夏普比率（Sharpe Ratio） 是最合适、最通用的“组合性价比”指标

return_stability
    年化波动率（Annualized Volatility）

style_balance:
    风格赫芬达尔指数（HHI）



调入和调出组合


就是做大这个雷达图，那么就需要从评分

方案1
    维度进行扩大
方案2
    投资组合优化，看最后的评分




链路

1. 先计算5维度
2. 综合评分
3. llm进行风险分析

---
投资组合的模拟

1. 压力测试
2. 调仓方案
3. 调仓逻辑
4. 新手建议
5. 常见问题

---

## 调仓建议（Rebalance）

### 功能入口

```python
from research.portfolio_advisor.rebalance import (
    load_candidate_pool_from_jsonl_as_pool,
    suggest_rebalance,
)

# 1. 加载候选池（从 JSONL 中读取，并自动拉取完整行情）
pool = load_candidate_pool_from_jsonl_as_pool(
    "research/portfolio_advisor/data/stock_dimension_scores.jsonl"
)

# 2. 生成调仓建议
plans = suggest_rebalance(
    current_dfs,
    current_weights,
    pool,
    objective="geometric_composite_score",
    max_actions=1,
    top_k=3,
)

# 3. 查看最优方案
best = plans[0]
print(f"当前得分: {best.score_before:.2f}")
print(f"调仓后得分: {best.score_after:.2f}")
for action in best.actions:
    print(f"建议: 调出 {action.code_out}，调入 {action.code_in}")
```

### 核心概念

| 概念 | 说明 |
|------|------|
| `RebalanceAction` | 一次调仓动作，当前主要实现 `replace`（1 对 1 替换）。 |
| `RebalancePlan` | 一套完整方案，包含调仓前后五维得分与目标得分对比。 |
| `CandidatePool` | 候选股票池，可由 JSONL 加载或从 FileVisitor 构建。 |
| `CurrentPortfolio` | 当前组合（codes / weights / dfs）。 |

### 优化目标

- `geometric_composite_score`（默认）：几何加权综合分，对低分项有惩罚。
- `composite_score`：算术加权综合健康分。
- `min_dimension_score`：最大化五维中的最低分。
- `dimension:<name>`：单独提升某一维度，如 `dimension:drawdown_control`。

### 权重策略

- `proportional`（默认）：调入标的继承调出权重，其余标的权重不变。
- `equal`：新组合内所有标的等权。
- `fixed_new_weight`：每只调入标的指定固定权重，其余标的等比例压缩。

### 约束与限制

- `max_actions`：单次最多同时替换几只股票，取值 `[1, 3]`，默认 `1`。
- `min_improvement`：最小可接受得分提升，低于该值的方案被过滤。
- `min_overlap_days`：可选，要求新组合重叠交易日数不低于阈值，避免日期交集过小导致指标失真。
- 不做多轮贪心迭代，单次搜索直接返回当前约束下的最优方案。

### 输出示例

```json
{
  "objective": "geometric_composite_score",
  "actions": [
    {"action_type": "replace", "code_out": "000858.SZ", "code_in": "600519.SH",
     "weight_out": 0.3, "weight_in": 0.3, "reason": "替换以提升目标得分，预计提升 5.7700"}
  ],
  "score_before": 42.35,
  "score_after": 48.12,
  "improvement": 5.77,
  "dimensions_before": {...},
  "dimensions_after": {...}
}
```

### 注意事项

1. `stock_dimension_scores.jsonl` 必须包含 `code` 字段；若缺失请重新运行 `one.py`。
2. 单股 `style_balance` 恒为 0，因此候选池预筛选不依赖该维度；最终方案均经 `compute_portfolio_dimensions` 全量重算验证。
3. 调仓建议基于历史数据计算，不构成投资建议。

