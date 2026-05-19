import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Union, Any

# 延迟导入：仅在函数内部使用，避免模块级依赖链

USER_PROFILE_TAGS = {
    "MOMENTUM_TRADER": "频繁交易且偏好近期强势标的",
    "SWING_TRADER": "持仓周期 2-10 天，关注技术形态",
    "DAY_TRADER_PATTERN": "交易集中在开盘后 1 小时内，日内了结倾向",
    "BUY_AND_HOLD": "交易频次极低，关注基本面与长期价值",
    "DIVIDEND_HUNTER": "频繁浏览/交易高股息标的",
    "SECTOR_ROTATOR": "频繁切换板块，跟随行业轮动",
    "CONTRARIAN_SIGNAL": "行为与市场情绪反向（如市场大跌时增加浏览）",

    "PRE_MARKET_SCOUT": "活跃时段在开盘前（本地时间 09:00 前）",
    "COMMUTE_READER": "碎片化阅读，短停留（<<30s）高点击",
    "DEEP_DIVE_READER": "长停留（>120s），偏好阅读完整长文",
    "HIGH_INTENT_LOW_CONVICT": "频繁浏览个股详情但极少交易",
    "PUSH_RESPONSIVE": "对推送通知点击率显著高于自然浏览",
    "LURKER": "低点击、低搜索、低交易，以被动消费为主",

    "BEGINNER_TERM_SEARCHER": "频繁搜索基础金融术语（\"什么是金叉\", \"市盈率怎么看\"）",
    "INTERMEDIATE_STRATEGY": "搜索/阅读涉及策略组合、板块轮动",
    "ADVANCED_INSTRUMENTS": "关注衍生品、 Greeks、对冲工具（仅允许作为客观观察，不推断实际交易权限）",

    "CONCENTRATION_RISK": "持仓/关注列表高度集中于单一板块（>60%）",
    "CHASING_MOMENTUM_DATA": "搜索与阅读大量触及 52 周高点的标的",
    "FREQUENT_WATCHLIST_CHURN": "关注列表高频增删（7日内变动 >50%）",

    "PRICE_ACTION_TRACKER": "价格走势、涨跌幅、技术点位、52周高低点、盘中异动。",
    "POLICY_REGULATION_WATCHER": "央行政策、监管动态、利率决策、政府表态、贸易政策。",
    "FUNDAMENTAL_DRIVEN": "财报数据、营收增长、盈利能力、基本面指标、业绩指引。",
    "GEOPOLITICAL_RISK_MONITOR": "地缘冲突、国际关系、供应链风险、宏观安全局势",
    "SECTOR_ROTATION_TRACKER": "行业轮动、板块趋势、产业链变化、竞争格局。",
    "SENTIMENT_MOOD_READER": "市场情绪、投资者心理、资金流向、舆论风向、恐惧/贪婪指标。",
    "EXECUTIVE_ACTION_WATCHER": "高管动向、公司战略、并购活动、股权变动、管理层言论。",
}


def build_user_profile_prompt(
        user_data: Dict,
        current_time: Optional[str] = None,
        market_context: Optional[str] = None,
        include_few_shot: bool = True,
        model_version: str = "llm-v2.1"
) -> Dict[str, str]:
    """
    构建用于 LLM 生成金融用户画像标签的完整 Prompt。

    返回包含 system + user 的字典，可直接用于 OpenAI / Claude / Qwen 等 Chat API。

    Args:
        user_data: 用户行为数据字典，必须包含 clickstream_7d, recent_news_browsing_7d 等字段
        current_time: 当前 ISO 时间，默认自动生成
        market_context: 当前市场环境上下文摘要，用于 LLM 校准时效性
        include_few_shot: 是否包含 Few-Shot 示例（生产环境可关闭以节省 Token）
        model_version: 模型版本号，写入 output schema

    Returns:
        {"system": "...", "user": "..."}
    """

    # === 1. 默认值处理 ===
    if current_time is None:
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if market_context is None:
        market_context = (
            "中东地缘冲突持续，美联储维持利率不变预期升温，"
            "港股科技板块波动率上升，AI 基础设施支出加速。"
        )

    # 计算输入数据哈希（用于 audit.inputDataHash）
    input_hash = hashlib.sha256(json.dumps(user_data, sort_keys=True).encode()).hexdigest()[:8]

    # === 2. System Prompt（角色、约束、Taxonomy、Output Schema） ===
    system_prompt = f"""# Role
你是一位受雇于国际商业银行的「金融用户画像分析师」。你的任务是基于脱敏后的客户行为数据与最近浏览的新闻内容，生成客观、可解释、可审计的用户画像标签。

# Core Mission
将输入的多源异构数据，推理为结构化的画像标签。标签必须仅描述用户的行为模式、内容偏好与客观风险敞口，**严禁包含任何投资建议、买卖意图预测或未来收益暗示**。

# Input Data Sources
你将收到以下一种或多种 JSON 格式的脱敏数据片段：
1. `clickstream_7d`: App 页面路径与停留时长序列
2. `search_logs_30d`: 站内搜索关键词与点击结果
3. `trade_history_30d`: 近30日成交记录（仅包含标的代码、交易方向、频次、时段，不含金额与盈亏）
4. `watchlist_snapshot`: 当前关注列表（仅含标的代码与添加时间）
5. `content_engagement_14d`: AI Insight 内容的阅读、分享、忽略记录
6. `rm_notes`: 客户经理人工录入的跟进摘要（已脱敏敏感信息）
7. `recent_news_browsing_7d`: 近7日用户在 App 内或关联资讯页浏览的新闻列表，包含标题、摘要、板块分类、浏览时间与停留时长

# Strict Constraints
1. **客观性原则**：只使用客观行为事实推导标签，禁止心理揣测（如"用户很焦虑"）。
2. **非投资建议**：严禁生成包含 "BUY", "SELL", "HOLD", "bullish", "bearish" 等倾向性词汇的标签。
3. **隐私红线**：禁止推断用户具体资产金额、家庭关系、婚姻状况、健康状况等非金融行为。
4. **可解释性**：每个标签必须附带 `evidence` 字段，列出具体的数据依据（如 "近7日阅读3篇关于中东冲突的新闻，平均停留 120 秒"）。
5. **置信度校准**：若数据稀疏或存在矛盾，必须降低置信度（<<0.6），并在 evidence 中说明不确定性。
6. **时效性**：所有标签必须设置 `expiresAt`（默认生成后 30 天），过期需重新推理。

# Tag Taxonomy（标签分类体系）

## A. 预定义分类（Closed Taxonomy）—— 必须从以下枚举中选择
这些标签描述用户的**行为模式、经验水平、互动习惯与新闻关注焦点**，不允许自由创造。

### A1. trading_style（交易风格）
- `MOMENTUM_TRADER`: 频繁交易且偏好近期强势标的
- `SWING_TRADER`: 持仓周期 2-10 天，关注技术形态
- `DAY_TRADER_PATTERN`: 交易集中在开盘后 1 小时内，日内了结倾向
- `BUY_AND_HOLD`: 交易频次极低，关注基本面与长期价值
- `DIVIDEND_HUNTER`: 频繁浏览/交易高股息标的
- `SECTOR_ROTATOR`: 频繁切换板块，跟随行业轮动
- `CONTRARIAN_SIGNAL`: 行为与市场情绪反向（如市场大跌时增加浏览）

### A2. engagement_pattern（互动模式）
- `PRE_MARKET_SCOUT`: 活跃时段在开盘前（本地时间 09:00 前）
- `COMMUTE_READER`: 碎片化阅读，短停留（<<30s）高点击
- `DEEP_DIVE_READER`: 长停留（>120s），偏好阅读完整长文
- `HIGH_INTENT_LOW_CONVICT`: 频繁浏览个股详情但极少交易
- `PUSH_RESPONSIVE`: 对推送通知点击率显著高于自然浏览
- `LURKER`: 低点击、低搜索、低交易，以被动消费为主

### A3. experience_level（经验水平信号）
- `BEGINNER_TERM_SEARCHER`: 频繁搜索基础金融术语（"什么是金叉", "市盈率怎么看"）
- `INTERMEDIATE_STRATEGY`: 搜索/阅读涉及策略组合、板块轮动
- `ADVANCED_INSTRUMENTS`: 关注衍生品、 Greeks、对冲工具（仅允许作为客观观察，不推断实际交易权限）

### A4. risk_signal（客观风险行为信号，非评级）
- `CONCENTRATION_RISK`: 持仓/关注列表高度集中于单一板块（>60%）
- `CHASING_MOMENTUM_DATA`: 搜索与阅读大量触及 52 周高点的标的
- `FREQUENT_WATCHLIST_CHURN`: 关注列表高频增删（7日内变动 >50%）

### A5. news_attention_focus（新闻关注焦点）【新增】
描述用户在阅读新闻时**具体关注的维度或角度**，而非宏观主题本身。需从新闻标题/摘要中的高频关键词、停留时长分布及阅读顺序推断。

- `PRICE_ACTION_TRACKER`: 重点关注价格走势、涨跌幅、技术点位、52周高低点、盘中异动。典型信号：标题含 "hits 52-week high", "surges", "plunges", "breakout" 且停留较长。
- `POLICY_REGULATION_WATCHER`: 重点关注央行政策、监管动态、利率决策、政府表态、贸易政策。典型信号：标题含 "Fed", "rate cut", "regulation", "tariff", "policy" 且反复阅读。
- `FUNDAMENTAL_DRIVEN`: 重点关注财报数据、营收增长、盈利能力、基本面指标、业绩指引。典型信号：标题含 "earnings", "revenue", "EPS", "guidance", "profit margin" 且停留较长。
- `GEOPOLITICAL_RISK_MONITOR`: 重点关注地缘冲突、国际关系、供应链风险、宏观安全局势。典型信号：标题含 "war", "conflict", "sanctions", "Middle East", "supply chain disruption"。
- `SECTOR_ROTATION_TRACKER`: 重点关注行业轮动、板块趋势、产业链变化、竞争格局。典型信号：频繁阅读跨板块对比类新闻，如 "Tech vs Energy", "sector rotation"。
- `SENTIMENT_MOOD_READER`: 重点关注市场情绪、投资者心理、资金流向、舆论风向、恐惧/贪婪指标。典型信号：标题含 "market sentiment", "fear", "greed", "inflows", "outflows", "volatility"。
- `EXECUTIVE_ACTION_WATCHER`: 重点关注高管动向、公司战略、并购活动、股权变动、管理层言论。典型信号：标题含 "CEO", "acquisition", "merger", "stake", "buyback", "executive"。

## B. 动态兴趣分类（Open Taxonomy）—— 由 LLM 基于新闻内容自动归纳
这些标签描述用户的**内容兴趣主题**，允许你从 `recent_news_browsing_7d` 的标题、摘要与板块中自主提取、归一化并命名。

### 命名与归一化规则
1. **主题命名**：使用英文大写下划线格式，如 `AI_SECTOR`, `MIDDLE_EAST_CONFLICT`, `RATE_POLICY`, `SEMICONDUCTOR_SUPPLY_CHAIN`, `HK_PROPERTY_MARKET`。
2. **语义归一化**：不同表述的同一主题必须合并。例如：
   - "美联储降息"、"FED rate cut"、"鲍威尔讲话"、"Interest Rate Policy" → 统一为 `RATE_POLICY`
   - "以伊冲突"、"中东局势"、"Iran war"、"Middle East Conflict" → 统一为 `MIDDLE_EAST_CONFLICT`
   - "英伟达财报"、"NVIDIA earnings"、"AI 芯片股" → 统一为 `AI_SECTOR`（若侧重技术）或 `SEMICONDUCTOR_SUPPLY_CHAIN`（若侧重产业链）
3. **粒度控制**：主题应在**板块级**或**宏观议题级**，禁止过细（如 `NVDA_Q1_2026_ER` 不被允许，应归一化为 `AI_SECTOR` 或 `SEMICONDUCTOR_SUPPLY_CHAIN`）。
4. **时效校准**：若用户仅在近2天内集中浏览某突发新闻（如 "中东冲突升级"），需降低置信度或缩短 `expiresAt`（如 7 天），因为兴趣可能是应激性而非持续性。
5. **交叉验证**：若新闻兴趣与 `watchlist_snapshot` 或 `trade_history` 中的持仓/交易标的重合，可提升置信度（如用户同时阅读 AI 新闻并持有 NVDA）。

### 动态标签输出格式
动态兴趣标签归入 `interest_topic` 分类，字段结构与预定义标签一致，但 `tag` 字段由你基于内容自主命名。

# Output Schema
你必须且只能输出一个合法的 JSON 对象，不要包含 markdown 代码块标记（如 ```json），不要添加任何解释性文字。

输出结构：
{{
  "generatedTags": [
    {{
      "tag": "<标签值>",
      "category": "<分类名：trading_style / engagement_pattern / experience_level / risk_signal / news_attention_focus / interest_topic>",
      "confidence": <0.0-1.0之间的浮点数，保留两位小数>,
      "evidence": "<基于输入数据的具体事实描述，必须引用具体新闻标题或搜索词>",
      "sourceData": "<输入数据源标识，如 clickstream_7d, recent_news_browsing_7d>",
      "modelVersion": "{model_version}",
      "generatedAt": "<当前ISO时间>",
      "expiresAt": "<当前时间+30天的ISO时间，若为主题兴趣且判断为短期应激，可缩短至7天>",
      "active": true
    }}
  ],
  "summary": {{
    "activeTagCount": <整数>,
    "lastGeneratedAt": "<当前ISO时间>",
    "categories": ["<<本次生成的分类名数组>"]
  }},
  "audit": {{
    "inputDataHash": "<输入数据的SHA256短哈希前8位>",
    "reasoningChain": "<一句话总结本次推理逻辑>"
  }}
}}

# Reasoning Steps（内部思考链，不输出）
在生成最终 JSON 前，请按以下步骤思考：
1. **数据对齐**：列出输入数据中的关键事实（交易频次、阅读时长、搜索关键词、新闻标题列表）。
2. **主题归纳**：对 `recent_news_browsing_7d` 的标题与摘要进行主题聚类：
   - 将同义/近义主题归一化为统一标签名
   - 统计每个主题下的阅读频次、总停留时长、最近阅读时间
   - 判断是持续性兴趣（近7日均匀分布）还是应激性关注（近1-2日突发集中）
3. **焦点识别（新增）**：分析用户在各主题新闻中的**关注角度**：
   - 提取标题/摘要中的高频关键词（如 "surges", "earnings", "Fed", "war", "sentiment"）
   - 对比同类主题新闻的停留时长：若用户阅读 "NVIDIA hits 52-week high"（60s）远长于 "AI Sector Rebounds"（95s），说明其更关注价格异动而非行业趋势
   - 若用户同时阅读同一标的的 "earnings" 和 "stock price" 新闻，比较停留时长以判断其是基本面驱动还是价格驱动
   - 将推断出的关注维度映射到 `news_attention_focus` 枚举值
4. **模式识别**：结合新闻兴趣、关注焦点与其他行为数据（如持仓、搜索）识别行为模式。
5. **冲突检查**：是否存在矛盾数据？若有，降低置信度或生成多个互斥标签。
6. **合规过滤**：检查每个候选标签是否违反 Constraints。
7. **时效校准**：应激性新闻兴趣设置短 `expiresAt`（7天），持续性兴趣设置标准 `expiresAt`（30天）。
"""

    # === 3. Few-Shot 示例（可选，节省 Token 时可关闭） ===
    few_shot_block = ""
    if include_few_shot:
        few_shot_block = f"""
# Few-Shot Example（示例）

## 输入示例
{{
  "clickstream_7d": [
    {{"page": "AI_INSIGHT_MACRO", "dwellSec": 180, "timestamp": "2026-05-10T08:15:00Z"}},
    {{"page": "AI_INSIGHT_MACRO", "dwellSec": 210, "timestamp": "2026-05-11T08:20:00Z"}},
    {{"page": "STOCK_DETAIL_NVDA", "dwellSec": 15, "timestamp": "2026-05-12T09:30:00Z"}},
    {{"page": "STOCK_DETAIL_NVDA", "dwellSec": 12, "timestamp": "2026-05-13T09:35:00Z"}}
  ],
  "search_logs_30d": [
    {{"query": "fed interest rate cut impact", "clicked": true}},
    {{"query": "what is golden cross", "clicked": true}}
  ],
  "trade_history_30d": [
    {{"symbol": "NVDA", "side": "BUY", "timestamp": "2026-05-12T09:32:00Z"}}
  ],
  "watchlist_snapshot": ["NVDA", "MSFT", "AAPL"],
  "content_engagement_14d": [
    {{"insightType": "MACRO", "action": "READ_FULL", "timestamp": "2026-05-10T08:15:00Z"}}
  ],
  "recent_news_browsing_7d": [
    {{"title": "How is the war with Iran impacting interest rates, money flow, and the stock market?", "summary": "Middle East Conflict: 2026 Market Pivot and Economic Re-Alignment...", "category": "Macro & Micro", "dwellSec": 185, "timestamp": "2026-05-10T08:15:00Z"}},
    {{"title": "AI Sector Rebounds: Strategic Partnerships and 'Physical AI' Pivot Drive 2026 Q2 Kickoff", "summary": "NVIDIA and Microsoft lead the charge as AI infrastructure spending accelerates...", "category": "Sector", "dwellSec": 95, "timestamp": "2026-05-11T09:20:00Z"}},
    {{"title": "President Trump suggests Iran war could be over in 'two or three weeks'", "summary": "Geopolitical de-escalation hopes trigger volatility in oil and defense sectors...", "category": "Geopolitics", "dwellSec": 140, "timestamp": "2026-05-12T07:30:00Z"}},
    {{"title": "Fed Chair Powell signals 'higher for longer' rate stance amid inflation concerns", "summary": "Federal Reserve maintains hawkish tone, pushing back against market expectations for June cut...", "category": "Central Bank", "dwellSec": 210, "timestamp": "2026-05-13T08:45:00Z"}},
    {{"title": "NVIDIA hits 52-week high as data center revenue surges 78%", "summary": "Strong earnings drive semiconductor stocks to new highs...", "category": "Stock News", "dwellSec": 60, "timestamp": "2026-05-14T10:00:00Z"}}
  ]
}}

## 输出示例
{{
  "generatedTags": [
    {{
      "tag": "MACRO_ORIENTED",
      "category": "engagement_pattern",
      "confidence": 0.92,
      "evidence": "近7日内2次访问 AI_INSIGHT_MACRO 页面，平均停留 195 秒；14天内阅读1篇 MACRO 长文。近7日浏览新闻中，3篇为宏观/地缘政治主题（'How is the war with Iran...', 'President Trump suggests Iran war...', 'Fed Chair Powell...'），累计停留 535 秒。",
      "sourceData": "clickstream_7d,content_engagement_14d,recent_news_browsing_7d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "POLICY_REGULATION_WATCHER",
      "category": "news_attention_focus",
      "confidence": 0.90,
      "evidence": "在宏观主题新闻中，对 'Fed Chair Powell signals higher for longer rate stance...' 停留最长（210秒，为所有新闻之最）；搜索记录包含 'fed interest rate cut impact'；同时阅读 'How is the war with Iran impacting interest rates...' 亦聚焦利率影响。表明用户关注政策对市场的传导机制，而非单纯的地缘冲突事件本身。",
      "sourceData": "recent_news_browsing_7d,search_logs_30d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "GEOPOLITICAL_RISK_MONITOR",
      "category": "news_attention_focus",
      "confidence": 0.82,
      "evidence": "浏览2篇直接涉地缘冲突新闻：'How is the war with Iran...'（停留 185s）与 'President Trump suggests Iran war could be over...'（停留 140s）。两篇均属 Geopolitics 分类，且阅读时间集中在早晨（07:30-08:15），呈现主动风险监控模式。但用户同时关注 'impact on interest rates'，说明其更关注冲突的经济传导而非军事进展本身。",
      "sourceData": "recent_news_browsing_7d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "PRICE_ACTION_TRACKER",
      "category": "news_attention_focus",
      "confidence": 0.65,
      "evidence": "浏览 'NVIDIA hits 52-week high as data center revenue surges 78%'（停留 60s），标题直接涉及价格异动（hits 52-week high）。但停留时间较短（60s，低于平均 138s），且该阅读发生在交易时段（10:00），可能为快速扫视价格信息。数据稀疏，置信度下调。",
      "sourceData": "recent_news_browsing_7d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "MIDDLE_EAST_CONFLICT",
      "category": "interest_topic",
      "confidence": 0.85,
      "evidence": "近7日内浏览2篇直接相关新闻：'How is the war with Iran impacting interest rates...'（停留 185s）与 'President Trump suggests Iran war could be over...'（停留 140s）。两篇均属 Geopolitics 分类，且阅读时间集中在早晨（07:30-08:15），呈现主动关注模式。",
      "sourceData": "recent_news_browsing_7d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "RATE_POLICY",
      "category": "interest_topic",
      "confidence": 0.88,
      "evidence": "搜索记录包含 'fed interest rate cut impact'；浏览新闻 'Fed Chair Powell signals higher for longer rate stance...' 停留 210 秒（为所有新闻中最长）；同时阅读 'How is the war with Iran impacting interest rates...' 亦涉及利率主题。多源交叉验证。",
      "sourceData": "search_logs_30d,recent_news_browsing_7d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "AI_SECTOR",
      "category": "interest_topic",
      "confidence": 0.72,
      "evidence": "浏览 'AI Sector Rebounds...'（停留 95s）与 'NVIDIA hits 52-week high...'（停留 60s）。但后者停留较短（60s），且用户持有 NVDA 并近期买入，可能为持仓驱动而非纯粹兴趣驱动。置信度适度下调。",
      "sourceData": "recent_news_browsing_7d,trade_history_30d,watchlist_snapshot",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "BEGINNER_TERM_SEARCHER",
      "category": "experience_level",
      "confidence": 0.75,
      "evidence": "搜索记录包含 'what is golden cross'，属于基础技术术语查询，且未伴随后续深度技术内容阅读。",
      "sourceData": "search_logs_30d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }},
    {{
      "tag": "HIGH_INTENT_LOW_CONVICT",
      "category": "engagement_pattern",
      "confidence": 0.68,
      "evidence": "2次浏览 NVDA 个股页（停留仅 15s、12s），但搜索与交易记录显示仅执行1次买入，浏览-交易转化率低。",
      "sourceData": "clickstream_7d,trade_history_30d",
      "modelVersion": "{model_version}",
      "generatedAt": "{current_time}",
      "expiresAt": "{(datetime.fromisoformat(current_time.replace('Z', '+00:00')) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
      "active": true
    }}
  ],
  "summary": {{
    "activeTagCount": 9,
    "lastGeneratedAt": "{current_time}",
    "categories": ["engagement_pattern", "news_attention_focus", "interest_topic", "experience_level"]
  }},
  "audit": {{
    "inputDataHash": "b7e2d9a1",
    "reasoningChain": "用户呈现强宏观与地缘政治兴趣，且对政策利率和地缘风险的经济传导尤为关注；AI 板块兴趣受持仓驱动；个股浏览频次高但停留短、转化低，呈现高意向低决断特征。"
  }}
}}
"""

    # === 4. 拼接完整 System Prompt ===
    full_system = system_prompt + few_shot_block

    # === 5. User Prompt（动态数据注入） ===
    user_prompt = f"""请基于以下脱敏用户数据，按照系统指令生成画像标签 JSON。

当前时间：{current_time}
市场环境上下文：{market_context}
输入数据哈希（用于审计）：{input_hash}

输入数据：
{json.dumps(user_data, ensure_ascii=False, indent=2)}

请直接输出合法 JSON，不要包含任何其他文字。
"""

    return {
        "system": full_system.strip(),
        "user": user_prompt.strip(),
        "meta": {
            "input_hash": input_hash,
            "current_time": current_time,
            "model_version": model_version,
            "few_shot_included": include_few_shot
        }
    }


# === 6. 便捷调用函数（直接返回单字符串，兼容非 Chat 模型） ===
def build_user_profile_prompt_string(
        user_data: Dict,
        current_time: Optional[str] = None,
        market_context: Optional[str] = None,
        include_few_shot: bool = True
) -> str:
    """
    将 system + user 合并为单个 prompt 字符串。
    适用于不支持 system/user 分离的模型，或简单场景。
    """
    prompts = build_user_profile_prompt(
        user_data=user_data,
        current_time=current_time,
        market_context=market_context,
        include_few_shot=include_few_shot
    )
    return f"{prompts['system']}\n\n---\n\n{prompts['user']}"



def gen_user_profile(user_id: str = "admin123"):
    """
    生成用户画像。

    1. 获取用户浏览历史
    2. 构造 recent_news_browsing_7d
    3. 调用 LLM 生成画像
    4. 保存到 MongoDB
    """
    print("\n[1/4] 获取用户浏览历史...")
    views_result = get_views_insight(user_id, page_size=50, page=1)
    view_items = views_result.get("items", [])
    print(f"      获取到 {len(view_items)} 条浏览记录")

    # 构造 recent_news_browsing_7d
    recent_news_browsing_7d = []
    for item in view_items:
        insight_id = item.get("insight_id")
        insight = item.get("insight") or get_insight_by_id(insight_id)
        if not insight:
            continue

        # 构造浏览数据，模拟 dwellSec（如果有的话，否则默认 60s）
        browse_entry = {
            "title": insight.get("content", "")[:100],
            "summary": insight.get("data_report", "") or insight.get("content", "")[:200],
            "category": _infer_category(insight),
            "dwellSec": item.get("dwellSec", 60),
            "timestamp": item.get("create_datetime", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        }
        recent_news_browsing_7d.append(browse_entry)

    for i, news in enumerate(recent_news_browsing_7d[:5], 1):
        print(f"      [{i}] {news['title'][:50]}... (停留 {news['dwellSec']}s)")

    # 构造 user_data
    print("\n[2/4] 构造 user_data 并生成 prompt...")
    user_data = {
        "recent_news_browsing_7d": recent_news_browsing_7d,
        "clickstream_7d": [],
        "search_logs_30d": [],
        "trade_history_30d": [],
        "watchlist_snapshot": [],
        "content_engagement_14d": [],
    }

    result = build_user_profile_prompt(
        user_data=user_data,
        market_context="中东地缘冲突持续，美联储维持利率不变预期升温。",
        include_few_shot=True,
    )

    print("\n[3/4] 调用 LLM 生成画像...")
    out_json = chat_once(result['system'] + result['user'])
    out_json = parse_json_from_llm(out_json)
    out_json['user_id'] = user_id
    out_json["datetime"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 保存到 MongoDB
    print("\n[4/4] 保存到 MongoDB...")
    inserted_id = save_user_profile(user_id, out_json)
    if inserted_id:
        print(f"      成功保存到 user_profiles, _id: {inserted_id}")
    else:
        print("      保存失败")

    return out_json


def _infer_category(insight: Dict[str, Any]) -> str:
    """
    从 insight 数据推断分类
    """
    data_label = insight.get("data_label", {})
    if isinstance(data_label, dict):
        # 尝试从 data_label 中提取主题
        topics = data_label.get("topics", [])
        if topics:
            return topics[0]
        sectors = data_label.get("sectors", [])
        if sectors:
            return sectors[0]
    return "General"