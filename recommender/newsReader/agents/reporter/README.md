# Reporter 模块使用文档（LLM驱动版）

## 概述

Reporter模块是**LLM驱动的**财经新闻写作智能体。与模板填充不同，它使用大型语言模型（LLM）根据分析结果"写作"，生成更自然、连贯、专业的财经文章。

## 核心特点

1. **LLM驱动写作**：不再是模板填充，而是让LLM根据分析数据创作
2. **多风格适配**：快讯、新闻、深度分析、研报各有专门的写作Prompt
3. **数据整合**：自动整合NER、标签、事件、多维度分析结果
4. **标准输出**：无论LLM如何写作，最终都输出标准格式的Article对象

## 工作流程

```
原始新闻 → NER提取 → 标签分类 → 事件结构化 → Analyst分析
                                              ↓
标准Article ← LLM写作 ← 写作Prompt + 分析数据整合
```

## 文件结构

```
reporter/
├── __init__.py          # 模块导出接口
├── models.py            # 数据模型定义（Article, StockInfo等）
├── prompts.py           # LLM写作Prompt集合 ★核心文件
├── writer.py            # ReportWriter（调用LLM生成）
├── templates.py         # 文章模板系统（备用）
├── formatter.py         # 格式化工具
└── README.md            # 本文档
```

## 写作Prompt类型

### 1. BASE_WRITING_PROMPT - 标准新闻
适用于一般财经新闻报道，生成结构完整的文章。

**输出要求**：
- 标题（30字以内）
- 副标题（50字以内）
- 摘要（200-300字）
- 正文（Markdown格式，包含引言、主体、结语）

### 2. FLASH_WRITING_PROMPT - 财经快讯
适用于突发新闻，强调时效性和简洁性。

**输出要求**：
- 标题（20字以内，突出核心数据）
- 正文（300-500字）
- 高信息密度

### 3. ANALYSIS_WRITING_PROMPT - 深度分析
适用于深度分析文章，整合多维度分析观点。

**输出要求**：
- 标题（引发思考）
- 摘要（300-400字，包含核心发现）
- 正文（2000-3000字）：
  - 事件/现象概述
  - 多维度深度分析（技术/基本面/资金/宏观）
  - 影响评估
  - 投资启示

### 4. RESEARCH_WRITING_PROMPT - 研究报告
适用于专业研报，风格严谨、数据详实。

**输出要求**：
- 投资要点（Executive Summary）
- 公司/行业概况
- 详细分析（财务/业务/估值）
- 盈利预测与投资建议
- 风险提示

## 使用方法

### 1. 基本使用（自动调用LLM）

```python
from research.newsReader.agents.reporter import ReportWriter, Article

# 创建Writer实例
writer = ReportWriter()

# 生成文章
article = writer.write(
    article_id="uuid-xxxx",
    original_content="新闻原文...",
    ner_data=ner_result,           # NER实体识别结果
    label_data=label_result,       # 标签分类结果
    event_data=event_result,       # 事件结构化结果
    analyst_data=analyst_result,   # 分析师分析结果
)

# 获取字典格式
article_dict = article.to_dict()
print(article_dict['title'])
print(article_dict['content'])
```

### 2. 指定文章类型

```python
from research.newsReader.agents.reporter import NewsType

# 强制生成深度分析
article = writer.write(
    ...,
    news_type=NewsType.ANALYSIS,
)

# 或指定模板
article = writer.write(
    ...,
    template_name="research",  # flash/news/analysis/research
)
```

### 3. 使用自定义LLM客户端

```python
# 如果你有自定义的LLM调用方式
def my_llm_client(prompt: str) -> str:
    # 你的LLM调用逻辑
    response = call_your_llm(prompt)
    return response

writer = ReportWriter(llm_client=my_llm_client)
article = writer.write(...)
```

### 4. 查看写作Prompt

```python
from research.newsReader.agents.reporter import (
    get_writing_prompt,
    FLASH_WRITING_PROMPT,
    ANALYSIS_WRITING_PROMPT,
)

# 获取特定类型的Prompt
prompt = get_writing_prompt("analysis")
print(prompt)

# 直接使用Prompt常量
print(ANALYSIS_WRITING_PROMPT)
```

## LLM输入数据格式

Writer会自动将所有分析数据格式化为以下结构供LLM使用：

```markdown
# 原始新闻内容

{新闻原文}

---

# 分析数据

## 1. 实体识别结果

- 实体1 [类型] -> 标准化名称 (股票代码)
- 实体2 [类型] -> 标准化名称
...

## 2. 分类标签

- 新闻类型: POLICY, EVENT
- 影响层级: MACRO, SECTOR
- 情感极性: POSITIVE (置信度: 0.92)
- 紧急度: P1_HIGH

## 3. 事件结构化

**主体-动作-客体关系：**
- 央行 宣布 降准：50bp

**影响范围：**
- 行业: 银行, 房地产
- 个股: 600036.SH, 000002.SZ
- 指数: 沪深300

**市场预期：**
- 预期: 降准25bp
- 实际: 降准50bp
- 预期差: 超预期

**历史相似事件：**
- 2024年1月24日央行降准 (相似度: 0.85)

## 4. 多维度分析

### 宏观分析师
**宏观经济趋势：** ...
**政策解读：** ...

### 基本面分析师
**财务分析：** ...
**估值评估：** ...

### 技术面分析师
**趋势分析：** ...
**支撑阻力：** ...

---

# 写作任务

请根据以上数据撰写一篇专业的财经文章...
```

## 输出格式

LLM需要以JSON格式输出：

```json
{
  "title": "文章标题",
  "sub_title": "副标题",
  "summary": "文章摘要（200-300字）",
  "content": "正文内容（Markdown格式，包含完整文章结构）",
  "tags": ["标签1", "标签2", "标签3"],
  "keywords": ["关键词1", "关键词2"],
  "sentiment": "positive/negative/neutral/mixed",
  "impact_level": "high/medium/low"
}
```

## 完整字段说明

### 必须字段（由LLM生成）
| 字段 | 说明 |
|------|------|
| `title` | 文章标题（30字以内） |
| `content` | 正文（Markdown格式） |

### 重要字段（由LLM生成）
| 字段 | 说明 |
|------|------|
| `sub_title` | 副标题（50字以内） |
| `summary` | 摘要（200-400字） |
| `tags` | 标签列表（5-10个） |
| `keywords` | 关键词（SEO用） |
| `sentiment` | 情感倾向 |
| `impact_level` | 影响等级 |

### 系统字段（由程序自动填充）
| 字段 | 说明 |
|------|------|
| `article_id` | 唯一ID |
| `publish_time` | 发布时间 |
| `create_time` | 创建时间 |
| `update_time` | 更新时间 |
| `stock_codes` | 关联股票（从NER提取） |
| `category_id` | 分类ID |
| `language` | 语言 |
| `status` | 状态 |

## 集成到主流程

```python
from research.newsReader.dev import analyst

# 分析新闻
result = analyst("新闻内容...")

# 获取完整的标准文章
article = result['article']

# 文章字段
print(article['title'])           # 标题
print(article['sub_title'])       # 副标题
print(article['summary'])         # 摘要
print(article['content'])         # Markdown正文
print(article['stock_codes'])     # 关联股票
print(article['tags'])            # 标签
print(article['sentiment'])       # 情感倾向
```

## 数据模型字段覆盖

**必须字段（5个）**：
- ✅ `article_id` - 程序生成
- ✅ `title` - LLM生成
- ✅ `content` - LLM生成
- ✅ `publish_time` - 程序生成
- ✅ `create_time` - 程序生成

**重要字段（9个）**：
- ✅ `sub_title` - LLM生成
- ✅ `summary` - LLM生成
- ✅ `source` - 可配置
- ✅ `category_id` - 从标签提取
- ✅ `stock_codes` - 从NER提取
- ✅ `slug` - 程序生成
- ✅ `update_time` - 程序生成
- ✅ `language` - 配置
- ✅ `tags/keywords` - LLM生成

**可选字段**：
- ✅ `sentiment` - LLM生成
- ✅ `impact_level` - LLM生成

## 写作质量优化建议

### 1. Prompt优化
如需要调整写作风格，可编辑 `prompts.py` 中的对应Prompt：

```python
# 修改写作要求
BASE_WRITING_PROMPT = """
# Role: 财经主笔
...
你的自定义写作要求...
"""
```

### 2. LLM选择
- **快讯**：使用快速模型（成本低，响应快）
- **深度分析**：使用强模型（如GPT-4，质量好）

### 3. 后处理
Writer会自动解析LLM输出，即使格式不完全标准也能处理：
- 支持纯JSON输出
- 支持Markdown代码块包裹的JSON
- 支持混合文本+JSON
- 备用方案：从文本提取字段

## 与模板版本的对比

| 特性 | 模板版本（v1.0） | LLM驱动版本（v2.0） |
|------|------------------|---------------------|
| 生成方式 | 模板填充 | LLM创作 |
| 内容质量 | 结构化但生硬 | 自然流畅 |
| 灵活性 | 固定格式 | 自适应内容 |
| 成本 | 低（无LLM调用） | 中（一次LLM调用） |
| 速度 | 快（本地处理） | 较慢（API调用） |
| 适用场景 | 大批量简单文章 | 精品内容 |

## 降级方案

如果LLM服务不可用，Writer会自动降级：
- 提取原始内容作为正文
- 使用原文前30字作为标题
- 标记为"LLM服务暂时不可用"

## 注意事项

1. **LLM Temperature**：建议在0.3-0.7之间，保证创意同时保持事实准确
2. **Token限制**：长文章可能需要分块生成
3. **事实校验**：LLM可能产生幻觉，重要数据需人工校验
4. **Prompt版本**：不同LLM对Prompt的理解可能不同，可能需要微调

## 扩展开发

### 添加新的写作风格

1. 在 `prompts.py` 中添加新的Prompt：

```python
CUSTOM_WRITING_PROMPT = """
# Role: 自定义角色
...
"""
```

2. 在 `get_writing_prompt` 函数中注册：

```python
def get_writing_prompt(news_type: str) -> str:
    prompts = {
        "flash": FLASH_WRITING_PROMPT,
        "news": BASE_WRITING_PROMPT,
        "analysis": ANALYSIS_WRITING_PROMPT,
        "research": RESEARCH_WRITING_PROMPT,
        "custom": CUSTOM_WRITING_PROMPT,  # 新增
    }
    return prompts.get(news_type, BASE_WRITING_PROMPT)
```

3. 使用：

```python
article = writer.write(..., template_name="custom")
```
