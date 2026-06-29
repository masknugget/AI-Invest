# 投资组合调仓（个股调入/调出）功能设计

> 目标：在已有 **五维诊断** 体系基础上，实现个股层面的“调入/调出”建议，使组合的五维得分 / 综合健康分 / 几何加权综合分得到可量化的提升。

---

## 1. 背景与目标

### 1.1 现有链路

当前 `research/portfolio_advisor/` 的链路为：

1. 输入：`List[pd.DataFrame]`（n 只标的日频行情） + `List[float]`（权重，和为 1）。
2. 计算：`result = compute_portfolio_dimensions(dfs, weights)`。
3. 输出：五维得分（0-100）、综合健康分（算术加权）、几何加权综合分。

五个维度：

| 维度 | 含义 | 计算基础 | 优化方向 |
|------|------|----------|----------|
| `drawdown_control` | 抗回撤能力 | 组合最大回撤 MDD | 越大越好 |
| `portfolio_diversification` | 资产分散度 | 有效下注数 ENB（weight-based） | 越大越好 |
| `position_efficiency` | 持仓性价比 | 组合夏普比率 | 越大越好 |
| `return_stability` | 收益稳定性 | 组合年化波动率 | 越大越好 |
| `style_balance` | 风格均衡 | 风格 HHI | 越大越好 |

### 1.2 本次目标

在 `research/portfolio_advisor/rebalance/` 目录下实现**个股调入/调出**逻辑：

- 给定当前组合（标的 + 权重）。
- 给定候选股票池（可从 `stock_dimension_scores.jsonl` 读取单股五维得分，也可从行情数据重新计算）。
- 输出一组调仓动作（调出 A，调入 B， optionally 调整权重），使得调仓后的组合得分更高。

### 1.3 关键约束

- 不得破坏现有 `compute_portfolio_dimensions` 接口。
- 调仓算法应支持“全量重算”与“启发式筛选”两种模式，便于在精度与性能之间切换。
- 输出必须是可解释、可验证的：包含调仓前后五维得分对比。
- 必须处理 `stock_dimension_scores.jsonl` **缺少股票代码**的问题（当前文件只存了得分，没有 `code` 字段）。

---

## 2. 现状盘点

### 2.1 代码结构

```text
research/portfolio_advisor/
├── dimension/
│   ├── run.py              # compute_portfolio_dimensions 入口
│   ├── run_one.py          # compute_stock_dimensions 单股入口
│   ├── drawdown_control.py
│   ├── portfolio_diversification.py
│   ├── position_efficiency.py
│   ├── return_stability.py
│   └── style_balance.py
├── rebalance/
│   └── __init__.py         # 当前为空，目标实现目录
├── data/
│   └── stock_dimension_scores.jsonl   # 100 只股票五维得分，但无 code
├── one.py                  # 生成 stock_dimension_scores.jsonl 的脚本
├── utils.py                # build_portfolio / save_jsonl / load_jsonl
└── docs/
    └── readme.md           # 产品功能说明
```

### 2.2 数据问题

当前 `one.py` 生成 `stock_dimension_scores.jsonl` 的逻辑：

```python
for df in tqdm(file_visitor.iter(), ...):
    result = compute_stock_dimensions(df)
    result_dict = result.to_score_dict()
    data_result.append(result_dict)
```

**问题**：`result_dict` 中没有股票代码。由于 `file_visitor.iter()` 的遍历顺序与外部调用方无法稳定对应，后续用该 JSONL 做候选池时无法知道每行属于哪只股票。

**解决方案**：在 `one.py`（或新的数据生成脚本）中写入 `code` 字段：

```python
result_dict = {
    "code": str(df["code"].iloc[0]),
    **result.to_score_dict(),
}
```

并建议额外保留生成日期窗口（`start_date`, `end_date`），便于后续追溯。

### 2.3 单股得分的局限性

`compute_stock_dimensions` 对单只股票强制令 `style_balance.score = 0`，且 `portfolio_diversification` 对单只股票永远是满分附近（因为只有 1 个资产）。

这意味着：

- `stock_dimension_scores.jsonl` 中的 `style_balance` 恒为 `0`，**不能用来直接比较个股风格贡献**。
- `portfolio_diversification` 在单股层面也失去区分度。

因此，**不能仅依赖单股五维得分做组合优化**。调仓效果必须通过 `compute_portfolio_dimensions(dfs_new, weights_new)` 重新验证。

---

## 3. 设计思路

### 3.1 核心矛盾

- **准确性**：组合五维得分是标的序列、权重、协方差、风格暴露的函数，任何调入/调出都必须重新计算组合得分。
- **计算量**：若当前组合有 N 只标的，候选池有 M 只股票，则“替换 1 只”的搜索空间为 `N × M`；每次替换都要重新跑五维诊断（含协方差、PCA、HHI 等），性能开销较大。

### 3.2 采用“两阶段”策略

```text
阶段 1：启发式筛选（快速粗排）
        用单股得分 / 简单指标快速筛出 Top-K 候选。

阶段 2：全量重算验证（精确校验）
        对 Top-K 候选逐一执行真实替换，调用 compute_portfolio_dimensions，
        选出综合得分提升最大的方案。
```

这样兼顾了可解释性（阶段 1 给出“为什么选这只候选股”）与准确性（阶段 2 用真实组合得分验证）。

### 3.3 优化目标

默认以 **几何加权综合分** 为主要优化目标：

```text
score_geo = Π (dim_score / 100) ^ w_dim * 100
```

原因：几何加权对低分项有惩罚，符合“短板决定生存”的投资逻辑；若任一维度为 0，则综合分为 0。

可选目标（由调用方指定）：

- `composite_score`：算术加权综合分。
- `geometric_composite_score`：几何加权综合分（默认）。
- `min_dimension_score`：最大化五维中的最低分（最短板补齐）。
- `dimension:<name>`：单独提升某一维度，例如 `dimension:drawdown_control`。

### 3.4 调仓动作定义与数量约束

一次调仓动作（`RebalanceAction`）包含：

```python
@dataclass
class RebalanceAction:
    action_type: Literal["remove", "add", "replace", "adjust_weight"]
    code_out: Optional[str] = None          # 调出标的
    code_in: Optional[str] = None           # 调入标的
    weight_out: float = 0.0                 # 调出权重（默认等权重新分配）
    weight_in: float = 0.0                  # 调入后权重
    reason: Optional[str] = None            # 调仓原因摘要
```

**调仓数量硬约束**：

- 单次建议的调入数量 ∈ `[1, 3]`，调出数量 ∈ `[1, 3]`。
- 调入数量与调出数量均不得超过当前组合标的个数 `N`。
- 默认单次仅做 **1 对 1 替换**；若用户明确需要，可扩展为最多 3 对 3。
- 不做多轮贪心迭代：一次搜索直接返回当前限制下的最优组合，避免过度优化和过拟合。

调仓方案（`RebalancePlan`）包含：

```python
@dataclass
class RebalancePlan:
    actions: List[RebalanceAction]
    portfolio_before: PortfolioDimensions
    portfolio_after: PortfolioDimensions
    score_before: float
    score_after: float
    improvement: float
    objective: str
```

---

## 4. 数据模型

### 4.1 候选股票池（CandidatePool）

```python
@dataclass
class StockCandidate:
    code: str
    df: pd.DataFrame              # 日频行情，含 date / close / pctChg 等
    dimension_scores: Dict[str, float]   # 单股五维得分（可选，用于快速筛选）
    industry: Optional[str] = None

class CandidatePool:
    candidates: List[StockCandidate]

    def from_jsonl(path: str) -> "CandidatePool": ...
    def from_file_visitor(limit: int = 1000) -> "CandidatePool": ...
```

### 4.2 当前组合（CurrentPortfolio）

```python
@dataclass
class CurrentPortfolio:
    codes: List[str]
    weights: List[float]
    dfs: List[pd.DataFrame]

    def to_dimensions(self) -> PortfolioDimensions:
        return compute_portfolio_dimensions(self.dfs, self.weights)
```

### 4.3 改进后的 JSONL 格式

建议 `one.py` 生成如下格式：

```jsonl
{"code": "000001.SZ", "start_date": "2023-01-01", "end_date": "2024-01-01", "drawdown_control": 11.27, "portfolio_diversification": 100.0, "position_efficiency": 6.02, "return_stability": 51.68, "style_balance": 0.0}
```

老文件若无法立即替换，调仓模块需兼容两种格式：

- 有 `code`：直接使用。
- 无 `code`：报错并提示重新生成数据。

---

## 5. 调仓算法

### 5.1 算法 1：受限组合搜索（默认）

**适用场景**：当前组合 N 较小（<=10），候选池 M 中等（<=500）。

**核心思想**：在“调入/调出数量均不超过 3、且不超过当前组合大小”的范围内，枚举所有合法的替换组合，逐一全量重算，返回得分提升最大的 Top-K 方案。**不执行多轮贪心迭代**，避免过度优化。

**参数**：

- `max_actions`：单次最多同时替换几只股票，取值范围 `[1, 3]`，默认 `1`。
- `max_actions` 必须满足 `max_actions <= len(current_codes)`。

**步骤**：

1. 计算当前组合得分 `S_current`。
2. 令 `k = min(max_actions, len(current_codes))`。
3. 枚举从当前组合中调出 `r` 只标的（`r` 从 1 到 `k`），并从候选池中调入 `a` 只股票（`a` 从 1 到 `k`，且 `a <= M`，`a <= N - r + 1`，保证组合非空）。
   - 默认且最常用的是 `r = a = 1`（1 对 1 替换）。
   - 若 `max_actions >= 2`，则额外支持 2 对 2、3 对 3 等对称替换；非对称调入/调出（如调 1 出 2）作为可选扩展。
4. 对每一种合法替换：
   - 构造新组合：移除 `r` 只原标的，加入 `a` 只候选股。
   - 权重处理：将调出权重按策略重新分配给剩余原标的 + 新调入标的，并归一化为和 1。
   - 调用 `compute_portfolio_dimensions(new_dfs, new_weights)` 得到新得分 `S_new`。
   - 记录 `improvement = S_new - S_current`。
5. 返回 improvement 最大的前 `top_k` 个方案（默认 `top_k=3`）。

**权重重新分配策略**（可选，由调用方指定）：

- `proportional`：调出权重按其余标的原权重比例分配（默认）。
- `equal`：调出权重平均分配给其余标的 + 新调入标的。
- `fixed_new_weight`：每只调入标的指定固定权重，其余标的等比例压缩。

### 5.2 算法 2：基于得分的快速启发式（用于候选池过大）

**适用场景**：候选池 M 很大（>1000），无法对每只股票做全量重算。

**步骤**：

1. 用单股维度得分对候选池粗排，筛出在各维度上表现优异的 Top-K 候选：
   - 例如：按 `drawdown_control + position_efficiency + return_stability` 加权排序，取 Top 100。
   - 预筛选**不使用** `style_balance`（单股恒为 0，无区分度）。
2. 对 Top-K 候选执行算法 1 的受限组合搜索，得到精确验证后的最优方案。

该算法仅作为性能优化入口，最终输出仍必须经过 `compute_portfolio_dimensions` 全量重算。

### 5.3 约束与过滤

调仓方案必须支持以下约束（后续可扩展）：

| 约束 | 说明 |
|------|------|
| `max_actions` | 单次最多同时替换几只股票，**取值范围 [1, 3]，且不得大于当前组合标的个数 N** |
| `min_improvement` | 最小得分提升阈值，低于则不建议调仓 |
| `turnover_limit` | 总换手率上限 |
| `industry_constraint` | 行业集中度上限（避免调入后某行业占比过高） |
| `blacklist` / `whitelist` | 禁止/强制候选池 |
| `keep_codes` | 必须保留的标的 |

当 `max_actions` 越界时，函数应自动截断为合法值并打印警告；若 `max_actions >= N`，则提示用户。

---

## 6. API 设计

### 6.1 主入口函数

```python
# research/portfolio_advisor/rebalance/engine.py

def suggest_rebalance(
    current_dfs: List[pd.DataFrame],
    current_weights: List[float],
    candidate_pool: List[StockCandidate],
    objective: str = "geometric_composite_score",
    max_actions: int = 1,
    min_improvement: float = 0.0,
    weight_strategy: str = "proportional",
    top_k: int = 3,
    verbose: bool = False,
) -> List[RebalancePlan]:
    """
    生成调仓建议。

    Parameters
    ----------
    current_dfs : List[pd.DataFrame]
        当前组合各标的行情数据。
    current_weights : List[float]
        当前组合权重，和应为 1。
    candidate_pool : List[StockCandidate]
        候选股票池。
    objective : str
        优化目标："composite_score" / "geometric_composite_score" / "min_dimension_score" / "dimension:<name>"。
    max_actions : int
        单次最多同时替换几只股票，取值范围 [1, 3]，且不得大于当前组合标的个数 N。默认 1。
        超过 3 时自动截断为 3；大于 N 时自动截断为 N；小于 1 时报错。
        不做多轮贪心迭代，仅在当前 max_actions 范围内做一次组合搜索。
    min_improvement : float
        最小可接受得分提升，低于该值的方案被过滤。
    weight_strategy : str
        权重再分配策略："proportional" / "equal" / "fixed_new_weight"。
    top_k : int
        返回前 K 个最优方案。
    verbose : bool
        是否打印中间过程。

    Returns
    -------
    List[RebalancePlan]
        按 improvement 降序排列的调仓方案列表。
    """
```

### 6.2 从 JSONL 加载候选池

```python
# research/portfolio_advisor/rebalance/loader.py

def load_candidate_pool_from_jsonl(
    path: str,
    require_code: bool = True,
) -> List[StockCandidate]:
    """
    从 stock_dimension_scores.jsonl 加载候选池。

    若 require_code=True 且某行缺少 code 字段，则抛出 ValueError。
    同时会尝试通过 FileVisitor 根据 code 拉取完整行情 DataFrame。
    """
```

### 6.3 工具函数

```python
# research/portfolio_advisor/rebalance/utils.py

def replace_stock(
    codes: List[str],
    weights: List[float],
    dfs: List[pd.DataFrame],
    code_out: str,
    candidate: StockCandidate,
    weight_strategy: str = "proportional",
) -> Tuple[List[str], List[float], List[pd.DataFrame]]:
    """执行一次替换，返回新组合的 codes / weights / dfs。"""

def evaluate_portfolio(
    codes: List[str],
    weights: List[float],
    dfs: List[pd.DataFrame],
    objective: str = "geometric_composite_score",
) -> Tuple[float, PortfolioDimensions]:
    """计算指定目标函数下的组合得分与完整诊断结果。"""
```

---

## 7. 输出格式示例

```json
{
  "objective": "geometric_composite_score",
  "current": {
    "codes": ["000001.SZ", "000002.SZ", "000333.SZ", "000858.SZ", "002415.SZ"],
    "weights": [0.1, 0.2, 0.3, 0.3, 0.1],
    "score": 42.35,
    "dimensions": {
      "drawdown_control": 65.0,
      "portfolio_diversification": 80.0,
      "position_efficiency": 55.0,
      "return_stability": 70.0,
      "style_balance": 0.0
    }
  },
  "plans": [
    {
      "actions": [
        {
          "action_type": "replace",
          "code_out": "000858.SZ",
          "code_in": "600519.SH",
          "weight_out": 0.3,
          "weight_in": 0.3,
          "reason": "调出后组合夏普与回撤控制提升显著"
        }
      ],
      "score_before": 42.35,
      "score_after": 48.12,
      "improvement": 5.77,
      "dimensions_after": {
        "drawdown_control": 72.0,
        "portfolio_diversification": 78.0,
        "position_efficiency": 62.0,
        "return_stability": 71.0,
        "style_balance": 5.0
      }
    }
  ]
}
```

---

## 8. 实现计划

### Phase 1：数据层补齐（高优先级）

1. 修改 `one.py`（或新建 `generate_stock_scores.py`），在 JSONL 中写入 `code`、`start_date`、`end_date`。
2. 提供 `load_candidate_pool_from_jsonl`，兼容新旧格式，无 code 时明确报错。
3. 将生成脚本与调仓模块解耦：调仓模块不依赖 `one.py` 的运行时行为，只依赖 JSONL 文件。

### Phase 2：核心调仓引擎（高优先级）

1. 实现 `replace_stock` 与 `evaluate_portfolio` 工具函数。
2. 实现 `suggest_rebalance` **受限组合搜索**：
   - 默认 `max_actions=1`，支持扩展至 `max_actions=3`。
   - 硬约束：调入/调出数量 ∈ `[1, 3]` 且 ≤ 当前组合大小。
   - 不做多轮贪心迭代，单次搜索返回最优方案。
3. 支持 `weight_strategy` 三种策略。
4. 支持 `objective` 至少两种：`geometric_composite_score` 与 `composite_score`。

### Phase 3：约束与过滤（中优先级）

1. 实现 `max_actions`、`min_improvement`、黑名单/白名单。
2. 接入 `industry_distribution.py` 或 `IndustryQuery`，实现行业集中度约束。
3. 实现换手率估算与上限控制。

### Phase 4：进阶优化（低优先级）

1. 在大候选池场景下，实现基于单股得分的 Top-K 预筛选，减少全量重算次数。
2. 支持非对称调入/调出（如调出 1 只、调入 2 只），但仍受 `max_actions <= 3` 限制。
3. 多目标帕累托前沿（Pareto frontier）展示，帮助用户在“收益 / 风险 / 分散度”之间权衡。

> 明确不做无限轮贪心迭代，避免过拟合与不可解释的组合漂移。

### Phase 5：测试与文档（高优先级）

1. 在 `test/` 下新增 `t_rebalance.py`：
   - 固定模拟数据断言替换后得分变化方向正确。
   - 断言权重归一化后总和为 1。
   - 断言约束过滤生效。
2. 更新 `docs/readme.md`，说明调仓功能入口与输出含义。

---

## 9. 风险与注意事项

### 9.1 数据对齐风险

- 候选股票行情 `df` 与当前组合 `df` 的日期区间可能不一致。`compute_portfolio_dimensions` 内部如何处理缺失日期？目前 `build_portfolio` 使用 inner join，若日期交集过小，组合指标会失真。
- **建议**：在调仓前统一要求所有 `df` 有足够长的重叠时间窗口（例如 >= 252 个交易日），不足时过滤或警告。

### 9.2 过拟合风险

- 基于历史行情优化的组合容易过拟合。调仓建议只能作为参考，不能直接用于实盘。
- **建议**：在输出中明确标注“基于历史数据计算，不构成投资建议”。

### 9.3 单股 `style_balance` 为 0

- 当前 `compute_stock_dimensions` 强制单股 `style_balance = 0`，所以用 JSONL 预筛选时无法评估个股对组合风格均衡的贡献。风格均衡只能在全量重算时获得。
- **建议**：候选池预筛时不使用 `style_balance`；最终方案必须经 `compute_portfolio_dimensions` 验证。

### 9.4 性能风险

- 若候选池 500 只、当前组合 10 只，单股替换需 5000 次全量五维计算，可能较慢。
- **建议**：
  - 默认先对候选池做快速预筛选（Top 100）。
  - 支持并行计算（`multiprocessing` 或 `joblib`）。
  - 提供 `max_candidates` 参数限制计算量。

---

## 10. 接口调用示例

```python
from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from research.portfolio_advisor.dimension.run import compute_portfolio_dimensions
from research.portfolio_advisor.rebalance.engine import suggest_rebalance
from research.portfolio_advisor.rebalance.loader import load_candidate_pool_from_jsonl

# 1. 当前组合
file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()
current_dfs = [file_visitor.random_one() for _ in range(5)]
current_weights = [0.1, 0.2, 0.3, 0.3, 0.1]

# 2. 候选池
candidates = load_candidate_pool_from_jsonl(
    "research/portfolio_advisor/data/stock_dimension_scores.jsonl"
)

# 3. 生成调仓建议
plans = suggest_rebalance(
    current_dfs,
    current_weights,
    candidates,
    objective="geometric_composite_score",
    max_actions=1,
    top_k=3,
)

# 4. 打印最优方案
best = plans[0]
print(f"当前得分: {best.score_before:.2f}")
print(f"调仓后得分: {best.score_after:.2f}")
for action in best.actions:
    print(f"建议: 调出 {action.code_out}，调入 {action.code_in}")
```

---

## 11. 结论

本次设计采用“**启发式筛选 + 单次受限组合搜索 + 全量重算验证**”的调仓框架：

- 以 `compute_portfolio_dimensions` 为唯一权威评分入口，保证五维得分的计算一致性。
- 以 **几何加权综合分** 为默认优化目标，兼顾短板效应。
- 调仓数量严格受限：调入/调出均不超过 3 只，且不超过当前组合大小；默认 1 对 1 替换。
- 不做多轮贪心迭代，单次搜索直接给出当前约束下的最优方案，降低过拟合风险。
- 先补齐 `stock_dimension_scores.jsonl` 的 `code` 字段，再实现 `rebalance/engine.py` 与 `rebalance/loader.py`。
- 通过权重策略、约束条件、Top-K 输出，使调仓建议可解释、可验证、可配置。

下一步：按“实现计划” Phase 1 → Phase 2 → Phase 5 的顺序落地代码。
