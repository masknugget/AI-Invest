"""
Reporter 模块 - 财经新闻写作智能体（LLM驱动版）

功能：
1. 接收analyst分析结果
2. 使用LLM生成高质量的财经文章
3. 支持多种文章类型（快讯、新闻、深度分析、研报）
4. 自动填充所有必需和重要字段

主要组件：
- models: 数据模型定义（Article, StockInfo等）
- prompts: LLM写作Prompt集合
- writer: 报告生成器核心（ReportWriter类，调用LLM生成）
- templates: 文章模板系统（备用）
- formatter: 格式化工具

使用示例：
    from research.newsReader.agents.reporter import ReportWriter, Article
    
    writer = ReportWriter()
    article = writer.write(
        article_id="xxx",
        original_content="新闻原文",
        ner_data=ner_result,
        label_data=label_result,
        event_data=event_result,
        analyst_data=analyst_result,
    )
    
    # 获取字典格式
    article_dict = article.to_dict()
"""

# 数据模型
from .models import (
    Article,
    ArticleStatus,
    NewsType,
    Sentiment,
    ImpactLevel,
    StockInfo,
    SourceInfo,
    ArticleMetadata,
    create_article,
)

# 报告生成器
from .writer import (
    ReportWriter,
    write_report,
)

# LLM写作Prompts
from .prompts import (
    get_writing_prompt,
    prepare_writing_context,
    format_ner_data,
    format_label_data,
    format_event_data,
    format_analyst_data,
    BASE_WRITING_PROMPT,
    FLASH_WRITING_PROMPT,
    ANALYSIS_WRITING_PROMPT,
    RESEARCH_WRITING_PROMPT,
)

# 模板系统（备用）
from .templates import (
    get_template,
    render_template,
    register_template,
    FLASH_TEMPLATE,
    NEWS_TEMPLATE,
    ANALYSIS_TEMPLATE,
    RESEARCH_TEMPLATE,
)

# 格式化工具
from .formatter import (
    format_article_content,
    generate_summary,
    generate_title,
    extract_keywords,
    word_count,
    reading_time,
    ContentValidator,
)

__all__ = [
    # 数据模型
    "Article",
    "ArticleStatus",
    "NewsType",
    "Sentiment",
    "ImpactLevel",
    "StockInfo",
    "SourceInfo",
    "ArticleMetadata",
    "create_article",
    
    # 报告生成器
    "ReportWriter",
    "write_report",
    
    # LLM写作Prompts
    "get_writing_prompt",
    "prepare_writing_context",
    "format_ner_data",
    "format_label_data",
    "format_event_data",
    "format_analyst_data",
    "BASE_WRITING_PROMPT",
    "FLASH_WRITING_PROMPT",
    "ANALYSIS_WRITING_PROMPT",
    "RESEARCH_WRITING_PROMPT",
    
    # 模板（备用）
    "get_template",
    "render_template",
    "register_template",
    "FLASH_TEMPLATE",
    "NEWS_TEMPLATE",
    "ANALYSIS_TEMPLATE",
    "RESEARCH_TEMPLATE",
    
    # 格式化工具
    "format_article_content",
    "generate_summary",
    "generate_title",
    "extract_keywords",
    "word_count",
    "reading_time",
    "ContentValidator",
]

__version__ = "2.0.0"  # LLM驱动版本
