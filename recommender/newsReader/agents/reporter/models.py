"""
Reporter 数据模型定义

定义财经新闻文章的标准数据结构和字段规范
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class ArticleStatus(Enum):
    """文章状态"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"       # 待审核
    PUBLISHED = "published"   # 已发布
    ARCHIVED = "archived"     # 已归档
    DELETED = "deleted"       # 已删除


class NewsType(Enum):
    """新闻类型"""
    FLASH = "flash"           # 快讯
    NEWS = "news"             # 新闻
    ANALYSIS = "analysis"     # 深度分析
    RESEARCH = "research"     # 研究报告
    OPINION = "opinion"       # 观点评论


class Sentiment(Enum):
    """情感标签"""
    POSITIVE = "positive"     # 正面
    NEGATIVE = "negative"     # 负面
    NEUTRAL = "neutral"       # 中性
    MIXED = "mixed"           # 多空交织


class ImpactLevel(Enum):
    """影响等级"""
    HIGH = "high"             # 高影响
    MEDIUM = "medium"         # 中等影响
    LOW = "low"               # 低影响


@dataclass
class StockInfo:
    """股票信息"""
    code: str                 # 股票代码，如 600519.SH
    name: str                 # 股票名称
    exchange: Optional[str] = None  # 交易所
    price: Optional[float] = None   # 当前价格
    change_pct: Optional[float] = None  # 涨跌幅


@dataclass
class SourceInfo:
    """来源信息"""
    name: str                 # 来源名称
    url: Optional[str] = None # 来源URL
    publish_time: Optional[str] = None  # 原始发布时间
    author: Optional[str] = None  # 原作者


@dataclass
class ArticleMetadata:
    """文章元数据（可选字段）"""
    # 情感与影响
    sentiment: Optional[Sentiment] = None
    sentiment_score: Optional[float] = None
    impact_level: Optional[ImpactLevel] = None
    
    # 交易信号（研报/投顾类）
    trading_signals: Optional[List[Dict[str, Any]]] = None
    
    # 多媒体
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    
    # 附件
    attachments: Optional[List[Dict[str, str]]] = None  # [{"name": "研报.pdf", "url": "..."}]
    
    # 访问控制
    is_paywall: bool = False
    access_level: str = "free"  # free/vip/premium
    region_restriction: Optional[List[str]] = None
    
    # 推送
    push_status: Optional[str] = None  # pending/sent/failed


@dataclass
class Article:
    """
    财经新闻文章标准数据模型
    
    字段分为：
    - 必须字段：article_id, title, content, publish_time, create_time
    - 重要字段：sub_title, summary, source, author, category_id, stock_codes, slug, update_time, language
    - 可选字段：metadata中的扩展字段
    """
    
    # ==================== 必须字段 ====================
    article_id: str           # 主键，唯一标识符（UUID或自增ID）
    title: str                # 标题，页面标题、SEO、列表展示核心
    content: str              # 正文内容，Markdown格式
    publish_time: datetime    # 发布时间，排序、定时发布依据
    create_time: datetime     # 创建时间，数据审计、排序兜底
    
    # ==================== 重要字段 ====================
    sub_title: Optional[str] = None      # 副标题，列表页摘要、SEO描述
    summary: Optional[str] = None        # 摘要，分享卡片文案
    
    source: Optional[SourceInfo] = None  # 来源信息（名称、URL、作者）
    
    category_id: Optional[str] = None    # 分类ID，导航、推荐、权限控制
    category_name: Optional[str] = None  # 分类名称
    
    stock_codes: List[StockInfo] = field(default_factory=list)  # 关联股票代码，财经差异化字段
    
    slug: Optional[str] = None           # SEO友好的URL标识
    seo_url: Optional[str] = None        # 完整SEO链接
    
    update_time: Optional[datetime] = None  # 更新时间，财经新闻常更新/勘误
    
    language: str = "zh-CN"              # 语言，多语言站点分水岭
    
    # ==================== 系统字段 ====================
    status: ArticleStatus = field(default=ArticleStatus.DRAFT)
    news_type: NewsType = field(default=NewsType.NEWS)
    
    # ==================== 内容扩展 ====================
    tags: List[str] = field(default_factory=list)  # 标签
    keywords: List[str] = field(default_factory=list)  # SEO关键词
    
    # ==================== 统计数据 ====================
    view_count: int = 0       # 阅读数
    like_count: int = 0       # 点赞数
    share_count: int = 0      # 分享数
    comment_count: int = 0    # 评论数
    
    # ==================== 元数据（可选字段集合） ====================
    metadata: ArticleMetadata = field(default_factory=ArticleMetadata)
    
    # ==================== 原始数据（用于追溯） ====================
    raw_data: Optional[Dict[str, Any]] = None  # 原始分析数据
    ner_data: Optional[Dict[str, Any]] = None  # NER数据
    label_data: Optional[Dict[str, Any]] = None  # 标签数据
    event_data: Optional[Dict[str, Any]] = None  # 事件数据
    analyst_data: Optional[Dict[str, Any]] = None  # 分析师数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于JSON序列化"""
        return {
            # 必须字段
            "article_id": self.article_id,
            "title": self.title,
            "content": self.content,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            
            # 重要字段
            "sub_title": self.sub_title,
            "summary": self.summary,
            "source": {
                "name": self.source.name if self.source else None,
                "url": self.source.url if self.source else None,
                "author": self.source.author if self.source else None,
            } if self.source else None,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "stock_codes": [
                {
                    "code": s.code,
                    "name": s.name,
                    "exchange": s.exchange,
                    "price": s.price,
                    "change_pct": s.change_pct,
                } for s in self.stock_codes
            ],
            "slug": self.slug,
            "seo_url": self.seo_url,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "language": self.language,
            
            # 系统字段
            "status": self.status.value,
            "news_type": self.news_type.value,
            
            # 内容扩展
            "tags": self.tags,
            "keywords": self.keywords,
            
            # 统计数据
            "view_count": self.view_count,
            "like_count": self.like_count,
            "share_count": self.share_count,
            "comment_count": self.comment_count,
            
            # 元数据
            "metadata": {
                "sentiment": self.metadata.sentiment.value if self.metadata.sentiment else None,
                "sentiment_score": self.metadata.sentiment_score,
                "impact_level": self.metadata.impact_level.value if self.metadata.impact_level else None,
                "trading_signals": self.metadata.trading_signals,
                "video_url": self.metadata.video_url,
                "audio_url": self.metadata.audio_url,
                "attachments": self.metadata.attachments,
                "is_paywall": self.metadata.is_paywall,
                "access_level": self.metadata.access_level,
                "region_restriction": self.metadata.region_restriction,
                "push_status": self.metadata.push_status,
            } if self.metadata else None,
        }
    
    @classmethod
    def from_analysis_result(
        cls,
        article_id: str,
        content: str,
        ner_data: Dict[str, Any],
        label_data: Dict[str, Any],
        event_data: Dict[str, Any],
        analyst_data: Dict[str, Any],
        generated_content: str,
    ) -> "Article":
        """
        从分析结果创建文章实例
        
        Args:
            article_id: 文章ID
            content: 原始新闻内容
            ner_data: NER识别结果
            label_data: 标签分类结果
            event_data: 事件结构化结果
            analyst_data: 分析师分析结果
            generated_content: 生成的文章正文
        """
        now = datetime.now()
        
        # 从NER数据提取股票代码
        stock_codes = []
        entities = ner_data.get("entities", [])
        for entity in entities:
            if entity.get("type") == "STOCK_CODE":
                stock_codes.append(StockInfo(
                    code=entity.get("stock_code", ""),
                    name=entity.get("normalized_name", ""),
                ))
        
        # 从标签数据提取情感
        sentiment = None
        classification = label_data.get("classification", {})
        sentiment_data = classification.get("sentiment", {})
        if sentiment_data:
            sentiment_label = sentiment_data.get("label", "NEUTRAL")
            sentiment = Sentiment(sentiment_label.lower())
        
        # 从事件数据提取来源信息
        source = None
        
        # 生成标题和摘要
        title = analyst_data.get("title", "财经新闻分析")
        summary = analyst_data.get("summary", "")
        
        # 生成slug
        slug = f"news-{article_id[:8]}"
        
        return cls(
            article_id=article_id,
            title=title,
            content=generated_content,
            publish_time=now,
            create_time=now,
            summary=summary,
            stock_codes=stock_codes,
            slug=slug,
            language="zh-CN",
            status=ArticleStatus.PUBLISHED,
            raw_data={
                "original_content": content,
            },
            ner_data=ner_data,
            label_data=label_data,
            event_data=event_data,
            analyst_data=analyst_data,
            metadata=ArticleMetadata(
                sentiment=sentiment,
            ),
        )


# 快捷创建函数
def create_article(
    title: str,
    content: str,
    article_id: Optional[str] = None,
    **kwargs
) -> Article:
    """
    快捷创建文章实例
    
    Args:
        title: 文章标题
        content: 文章内容
        article_id: 文章ID（可选，自动生成）
        **kwargs: 其他字段
    
    Returns:
        Article实例
    """
    import uuid
    
    now = datetime.now()
    
    if article_id is None:
        article_id = str(uuid.uuid4())
    
    return Article(
        article_id=article_id,
        title=title,
        content=content,
        publish_time=kwargs.get("publish_time", now),
        create_time=now,
        **kwargs
    )


# ============================================================================
# 函数式构造器
# ============================================================================

def make_stock_info(
    code: str,
    name: str,
    exchange: Optional[str] = None,
    price: Optional[float] = None,
    change_pct: Optional[float] = None,
) -> StockInfo:
    """纯函数：创建股票信息"""
    return StockInfo(
        code=code,
        name=name,
        exchange=exchange,
        price=price,
        change_pct=change_pct,
    )


def make_source_info(
    name: str,
    url: Optional[str] = None,
    publish_time: Optional[str] = None,
    author: Optional[str] = None,
) -> SourceInfo:
    """纯函数：创建来源信息"""
    return SourceInfo(
        name=name,
        url=url,
        publish_time=publish_time,
        author=author,
    )


def make_article_metadata(
    sentiment: Optional[Sentiment] = None,
    sentiment_score: Optional[float] = None,
    impact_level: Optional[ImpactLevel] = None,
    trading_signals: Optional[List[Dict[str, Any]]] = None,
    video_url: Optional[str] = None,
    audio_url: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None,
    is_paywall: bool = False,
    access_level: str = "free",
    region_restriction: Optional[List[str]] = None,
    push_status: Optional[str] = None,
) -> ArticleMetadata:
    """纯函数：创建文章元数据"""
    return ArticleMetadata(
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        impact_level=impact_level,
        trading_signals=trading_signals,
        video_url=video_url,
        audio_url=audio_url,
        attachments=attachments,
        is_paywall=is_paywall,
        access_level=access_level,
        region_restriction=region_restriction,
        push_status=push_status,
    )


def make_article(
    article_id: str,
    title: str,
    content: str,
    sub_title: Optional[str] = None,
    summary: Optional[str] = None,
    source: Optional[SourceInfo] = None,
    category_id: Optional[str] = None,
    category_name: Optional[str] = None,
    stock_codes: Optional[List[StockInfo]] = None,
    slug: Optional[str] = None,
    language: str = "zh-CN",
    status: ArticleStatus = ArticleStatus.DRAFT,
    news_type: NewsType = NewsType.NEWS,
    tags: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    metadata: Optional[ArticleMetadata] = None,
    **kwargs
) -> Article:
    """
    纯函数：完整构造文章
    
    自动处理时间字段，如果没有提供则使用当前时间
    """
    now = datetime.now()
    
    return Article(
        article_id=article_id,
        title=title,
        content=content,
        publish_time=kwargs.get("publish_time", now),
        create_time=kwargs.get("create_time", now),
        update_time=kwargs.get("update_time", now),
        sub_title=sub_title,
        summary=summary,
        source=source,
        category_id=category_id,
        category_name=category_name,
        stock_codes=stock_codes or [],
        slug=slug,
        language=language,
        status=status,
        news_type=news_type,
        tags=tags or [],
        keywords=keywords or [],
        metadata=metadata or ArticleMetadata(),
        **{k: v for k, v in kwargs.items() if k not in ["publish_time", "create_time", "update_time"]}
    )


# ============================================================================
# 函数式转换器
# ============================================================================

def article_to_json(article: Article) -> str:
    """纯函数：将文章转为JSON字符串"""
    import json
    return json.dumps(article.to_dict(), ensure_ascii=False, indent=2)


def json_to_article(json_str: str) -> Article:
    """纯函数：从JSON字符串解析文章"""
    import json
    data = json.loads(json_str)
    return Article(**data)
