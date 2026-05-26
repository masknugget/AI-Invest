def prompt_align_data(data_dict):
    data_str = f"""
# Role
你是一位专业的金融数据结构化工程师，擅长将非结构化的行业分析报告和事件数据提取为标准化的金融资讯字段。

# Task
基于以下多模态输入数据，生成一个严格符合格式的 JSON 对象。输入包含：
1. `data_report` — 综合报告正文（Markdown格式）
2. `IndustryAgent` — 深度行业分析（含10步推理链）
3. `data_ner` — 命名实体识别结果
4. `data_label` — 新闻分类标签
5. `data_event` — 事件关系与影响范围

# Output Schema
请严格按照以下字段生成，缺失值用 null 或空数组/空字符串表示：

{{
    "title": "str — 从data_report标题或核心结论提取，20字以内，突出事件+影响",
    "sub_title": "str — 从data_report副标题或Step 1重要性判断提取，40字以内，补充量化数据",
    "summary": "str — 从data_report核心结论前置部分提取，200字以内，包含事件、数据、影响方向",
    "content": "str — 将data_report正文去Markdown表格/代码块后转为纯文本，保留关键数据；若data_report为空则取IndustryAgent全文",
    "source": {{
        "name": "str — 固定为'市场监管总局'或从data_ner中CENTRAL_BANK实体提取",
        "url": "str — 若无可填null",
        "publish_time": "str — 从data_event或data_label中推断，格式'2024-06-XX'"
    }},
    "category_id": "str — 从data_label.classification.news_type主标签映射：POLICY→'policy', EVENT→'event'",
    "category_name": "str — 中文映射：POLICY→'政策监管', EVENT→'行业事件'",
    "stock_codes": [
        {{
            "code": "str — 股票代码",
            "name": "str — 公司名称",
            "market": "str — 'SH'/'SZ'/'BJ'",
            "impact": "str — 'positive'/'negative'/'neutral'",
            "reason": "str — 50字以内影响逻辑"
        }}
    ],
    "slug": "str — URL友好的英文标识，如'civil-drone-recall-regulation-2024'",
    "seo_url": "str — 完整SEO路径，如'/news/civil-drone-recall-regulation-2024'",
    "language": "str — 固定'zh-CN'",
    "news_type": "str — 从data_label.classification.news_type取置信度最高的label",
    "tags": ["str — 从data_ner实体类型+data_label影响级别组合，如'无人机','低空经济','政策监管','召回管理'],
    "keywords": ["str — 从data_ner实体文本+IndustryAgent高频词，如'市场监管总局','缺陷信息','车规级芯片'],
    "create_time": "str — 当前处理时间，格式'2024-06-26 14:30:00'",
    "publish_time": "str — 从data_event或source推断，格式同上",
    "metadata": {{
        "impact_level": ["str — data_label.classification.impact_level所有label"],
        "sentiment": "str — data_label.classification.sentiment.label",
        "urgency": "str — data_label.classification.urgency.label",
        "time_attr": "str — data_label.classification.time_attr.label",
        "affected_industries": ["str — data_event.affected_scope.industries"],
        "confidence": "float — data_label.overall_confidence",
        "event_id": "str — data_event.event_id",
        "routing_agents": ["str — data_router.routing_plan.primary_agents中的agent名"],
        "original_ner_count": "int — data_ner.entities数量",
        "has_recall_data": "bool — 是否包含召回数据(true)"
    }}
}}

# Extraction Rules
1. **stock_codes**：从IndustryAgent Step 8（A股标的映射）和Step 4（产业链图谱）提取所有提到的A股标的，结合`影响方向`判断impact字段。必须包含：敏芯股份(688286)、晶晨股份(688099)、航天彩虹(002389)、纵横股份(688070)、中科星图(688568)、海康威视(002415)。代码前缀：688→SH，002/000→SZ。
2. **title**：必须包含"无人机"和"召回"关键词，参考data_report主标题风格。
3. **sub_title**：必须包含量化数字"579例"和"2797台"。
4. **tags**：必须包含'低空经济'、'无人机'、'召回监管'。
5. **keywords**：必须包含'市场监管总局'、'缺陷信息'、'车规级认证'。
6. **metadata**：完整保留原始分类置信度和路由信息，便于下游系统追溯。
7. **content**：保留所有关键推理链和量化数据，但移除Mermaid图表语法和复杂表格，转为段落描述。

# Input Data
{data_dict}

# Output Requirement
仅输出合法的JSON对象，不要任何解释性文字，不要Markdown代码块包裹。
    
"""
    return data_str