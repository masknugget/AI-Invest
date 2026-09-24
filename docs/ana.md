 调用链路（从 dev.py 开始）

   ```
     dev.py (顶层脚本, for 循环遍历 news[500:])
     │  ① pandas 读 D:\BaiduNetdiskDownload\财经新闻\新浪财经新闻-2025\*.csv (gbk)
     │  ② app.core.database.get_mongo_db_sync() 取 MongoDB 连接
     ▼
     consumer/news.py:15  pipeline_news(content)
     │  ③ utils.gen_uuid() + datetime → article_id / create_time
     │
     │  ── 阶段1: 三路并行提取（实际是串行各一次 LLM 调用）
     │  ├── agents/pipelines/ner.py      prompt_ner()      → chat_once() → 文本
     │  ├── agents/pipelines/labels.py   prompt_labels()   → chat_once() → 文本
     │  └── agents/pipelines/event.py   prompt_event()    → chat_once() → 文本
     │
     │  ── 阶段2: 路由
     │     pipelines/router.py prompt_router() + 新闻+ner+label+event 拼成 p_data
     │     → chat_once() → utils.parse_json_from_llm()
     │     → routing_plan.primary_agents[]（如 ["MicroAgent","ValuationAgent"]）
     │
     │  ── 阶段3: 分析 Agent（按路由结果逐个串行调用）
     │     agents/analyst/factory.py create_analyst(name)
     │     ├── MacroAgent       → agents/analyst/macro_analyst.py       prompt_macro()
     │     ├── IndustryAgent    → agents/analyst/industry_analyst.py    prompt_industry()
     │     ├── MicroAgent       → agents/analyst/micro_analyst.py       prompt_micro()
     │     ├── EventAgent       → agents/analyst/repurchase_analyst.py  prompt_repurchase()
     │     ├── TechnicalAgent   → agents/analyst/symbol/technical_analyst.py   prompt_technical()
     │     ├── DividendAgent    → agents/analyst/symbol/high_dividend_analyst.py prompt_high_dividend()
     │     ├── FundamentalAgent → agents/analyst/symbol/fundamental_analyst.py   prompt_fundamental()
     │     ├── PortfolioAgent   → agents/analyst/portfolio_analyst.py   prompt_portfolio()
     │     └── ...（每个都是 prompt 模板函数，返回纯 prompt 字符串）
     │     → 每个 Agent: chat_once(p_data + prompt)  结果存入 out_data[name]
     │
     │  ── 阶段4: 报告
     │     agents/report.py prompt_report() + 新闻 + 各 Agent 输出
     │     → chat_once() → data_report ⚠️ 只拼接了 content[0]（第一个 Agent 的输出）
     │
     │  ── 阶段5: 结构化对齐
     │     agents/reporter/align_data.py prompt_align_data(json.dumps(out_data))
     │     → chat_once() → parse_json_from_llm() → data_align
     │     → 附加 article_id / create_time
     │
     ▼ 返回 out_data（dict）
     dev.py: collection.insert_one(out_data) → MongoDB insight_agg


---

● 先量化一下瓶颈：pipeline_news 内部是 6~10 次串行 LLM 调用，单次 RTT 按 2~5 秒算，一条新闻就要 15~50 秒。而且结构上真正必须串行的只有一半——NER / 标签 / 事件提取三路互相独立，路由
也只依赖这三者的结果。

针对"MCP 平台调用"这个场景，有四类方案，可以组合使用：

方案一：拆分成多个 MCP 工具，把并行度交给客户端（推荐先做）

把单体 analyze_news 拆成流水线式的工具集，MCP 客户端（LLM Agent）自己就能并行调度：

```
 extract_news_meta(content)     → 一次调用并行返回 ner + label + event（服务端 asyncio.gather）
 route_news_analysis(content, ner, label, event) → 返回 routing_plan（选中哪些 Agent）
 run_news_analyst(content, meta, agent_name)     → 单个 Agent 分析，客户端对多个 agent_name 并行调用
 generate_news_report(content, meta, analyses)   → 综合报告
 finalize_news_analysis(content, report, meta)   → 结构化对齐（返回最终 JSON，可选入库）
```

收益：
• 原来服务端串行的 3 路提取变 1 次调用（内部 asyncio.gather 并行，省 2/3 时间）
• 多个分析 Agent 由客户端并行发起（服务端用 asyncio.Semaphore 限并发，防止打爆 API 限流）
• 客户端可以只选需要的 Agent（比如只要 SentimentAgent），实现按需降级——一条新闻从 8 次调用减到 3 次
• 符合 MCP 的"小工具组合"哲学，stock_analysis.py 现有的单工具风格也能保留一个 analyze_news_fast 作为便捷封装

代价：客户端（LLM）需要多轮编排，prompt 里要把工具调用顺序讲清楚（写进 mcp.instructions）；单次会话 token 变多。

方案二：服务端并发化 + 队列异步化（平台化正解）

如果你希望客户端仍然只调一次 analyze_news：

1. 服务端并行：pipeline_news 重构为 async，ner/labels/event 三路 asyncio.gather，Agent 阶段用 gather + Semaphore(3~5)——单条新闻从串行 8 次降到约 4 个"波次"，耗时直接砍半
2. 异步任务模式：analyze_news(content) 立即返回 task_id（分析任务入 Redis 队列，app/services/queue/ 已有现成机制），新增 get_news_analysis_status(task_id) /
  get_news_analysis_result(task_id) 工具让客户端轮询。平台侧体验：先答"分析已提交"，过一分钟再取结果。这是生产环境的标准做法，也天然支持批量
3. 进度推送：MCP 支持 SSE/streamable-http 传输，可以做 subscribe_news_progress(task_id) 推送阶段进度（提取完成→路由完成→Agent 3/5→报告完成）

代价：实现复杂度最高，需要任务状态存储（Redis）和结果落库（已有 insight_agg）。

方案三：结果缓存与增量复用（成本+速度双赢）

• 内容 hash 缓存：md5(content) 作为 key，Redis 缓存 24h，重复新闻（转载通稿极多）直接命中，接近 0 耗时
• 阶段级缓存：NER/标签结果按内容缓存，换 Agent 组合时不用重跑前置阶段
• 同源新闻去重：转载新闻先做 SimHash 相似度判重，相似度 >0.9 直接复用原分析

方案四：模型分级（cheap routing）

现在所有阶段都用同一个模型。实际上：
• NER / 标签 / 事件提取 / 结构化对齐 → 用更小更快的模型（qwen-flash 级别）
• 只有分析 Agent 和报告 → 用大模型
 配合 DashScope 的 enable_thinking=False（如果底层是 qwen3 系）还能再省推理时间。

建议路线

第一步（半天工作量，收益最大）：方案一 + 方案四——拆工具、asyncio.gather 并行提取、提取阶段换小模型。单条新闻从 ~40s 降到 ~15s，且客户端可降级调用。

第二步：加方案三的 Redis 缓存，重复请求近零耗时。

第三步（如果要批量处理）：方案二的异步队列 + 轮询工具。

要不要我按第一步实施？拆分工具时会顺带把 pipeline_news 重构成 async 版本作为这些工具的内部实现。


---

 ● 对，这是很关键的一个优化方向——把"理解和写作"留给平台侧的大模型，MCP 工具只负责"它做不了的事"（结构化提取、确定性流水线）。平台调用方本身就有 LLM，它完全有能力做综合和总结，没必要
   在服务端再花 2~3 次大模型调用做一遍。

   核心思路：服务端只产出"原料"，平台 LLM 做"烹饪"

   现在 pipeline_news 里有两个阶段本质上是"写作任务"，可以转移：

   ┌────────────────────────┬────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
   │ 阶段                   │ 现状（服务端 LLM） │ 优化后                                                                                                                          │
   ├────────────────────────┼────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ 综合报告 prompt_report │ 服务端第 7 次调用  │ 平台 LLM 自己写。工具只返回各 Agent 分析结果，平台 LLM 结合自己的对话上下文总结——它本来就要把结果组织成回复给用户               │
   ├────────────────────────┼────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ 结构化对齐 align_data  │ 服务端第 8 次调用  │ 两个选择：① 平台 LLM 按给定 JSON Schema 输出（省一次调用，但格式稳定性略降）；② 保留在服务端（推荐，schema 严格，还能顺带入库） │
   └────────────────────────┴────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

   进一步，路由决策也可以转移。router 阶段的规则是确定性的（impact_level 含 MACRO → MacroAgent），平台 LLM 看到 data_label 后自己就能决定调用哪几个 run_news_analyst，服务端连路由那
   次调用都省掉——把路由规则写进 mcp.instructions 即可。

   优化后的工具集（3 个）

   ```
     extract_news_meta(content)
       服务端：ner + label + event 三路并行（asyncio.gather），1 次往返
       返回：三个结构化 JSON（已 parse，不是文本）
       ── 平台 LLM 读完 label 后，按 instructions 里的规则自行决定激活哪些 Agent

     run_news_analyst(content, meta, agent_name)
       服务端：单个 Agent 分析，1 次调用
       平台 LLM 可对多个 agent_name 并行发起多个 MCP 调用

     finalize_news_analysis(content, meta, analyses)
       服务端：结构化对齐 + 可选入库 insight_agg，1 次调用
       （可选；如果平台只要对话式回答，这步可以整个跳过）
   ```

   一次典型调用的对比

   优化前（单体 analyze_news）：服务端 8 次串行 LLM 调用 ≈ 40s，平台 LLM 只拿到最终结果，无法中途干预。

   优化后：
   • 轻量路径（只要解读）：extract_news_meta + 1~2 个 run_news_analyst，服务端 2~3 次调用、且有并行，约 8~12s，总结由平台 LLM 免费完成
   • 完整路径：4~6 次服务端调用 ≈ 15~20s，比原来快一半以上
   • 平台 LLM 获得了中途决策权：可以追问、可以只挑关心的 Agent、可以把多次新闻分析的结果跨条对比综合——这是单体工具给不了的

   给平台 LLM 的 instructions 示例（写进 mcp.instructions）

   ```
     analyze_news 工具使用流程：
     1. 调用 extract_news_meta 获取结构化标签
     2. 根据 data_label 路由（规则：MACRO→MacroAgent；COMPANY→MicroAgent；
        EARNINGS→MicroAgent+ValuationAgent；EVENT_REPO→EventAgent；
        EQUITY&P1→SentimentAgent；不确定时选 MicroAgent+SentimentAgent）
     3. 并行调用 run_news_analyst（每个 agent 一次）
     4. 综合各 Agent 输出与用户问题生成中文解读报告（由你完成，勿再请求服务端总结）
     5. 仅当用户要求保存/需要结构化数据时调用 finalize_news_analysis
   ```

   其他配合优化

   • 工具返回精简数据：不要返回 prompt 全文（现有 stock_analysis.py 就返回 prompt+data，浪费 token 且慢），只返回 parse 后的 JSON
   • 服务端缓存按内容 hash：平台侧多轮对话中重复引用同一新闻时直接命中
   • extract_news_meta 用小模型：NER/打标不需要大模型，能再快 30~50%

   这个方案的本质是把 MCP 从"远程函数"变成"远程数据源"，编排和表达交给本来就在运行的平台 LLM——这也是 Anthropic/OpenAI 对 MCP 工具设计的推荐粒度。要我按这个方案实施吗？