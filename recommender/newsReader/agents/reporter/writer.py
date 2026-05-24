"""
报告生成器核心

使用LLM根据analyst分析结果生成高质量的财经文章
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import re

from .models import (
    Article, ArticleStatus, NewsType, Sentiment, ImpactLevel,
    StockInfo, SourceInfo, ArticleMetadata, create_article
)
from .prompts import (
    get_writing_prompt,
    prepare_writing_context,
    format_ner_data,
    format_label_data,
    format_event_data,
    format_analyst_data,
)


class ReportWriter:
    """
    财经报告生成器 - LLM写作版本
    
    功能：
    1. 接收分析数据（NER、标签、事件、分析师结果）
    2. 选择合适的写作Prompt
    3. 调用LLM生成专业文章
    4. 解析LLM输出并填充Article对象
    """
    
    def __init__(
        self,
        llm_client=None,
        default_language: str = "zh-CN",
        default_source: Optional[str] = None,
    ):
        self.llm_client = llm_client
        self.default_language = default_language
        self.default_source = default_source
    
    def write(
        self,
        article_id: str,
        original_content: str,
        ner_data: Dict[str, Any],
        label_data: Dict[str, Any],
        event_data: Dict[str, Any],
        analyst_data: Dict[str, Any],
        news_type: Optional[NewsType] = None,
        template_name: Optional[str] = None,
    ) -> Article:
        """
        使用LLM根据分析数据生成完整文章
        
        Args:
            article_id: 文章唯一ID
            original_content: 原始新闻内容
            ner_data: NER实体识别结果
            label_data: 标签分类结果
            event_data: 事件结构化结果
            analyst_data: 分析师分析结果
            news_type: 新闻类型（自动判断或指定）
            template_name: 指定模板名称（可选）
        
        Returns:
            完整的Article对象
        """
        # 1. 判断新闻类型
        if news_type is None:
            news_type = self._determine_news_type(label_data, analyst_data)
        
        # 2. 获取写作Prompt
        writing_prompt = get_writing_prompt(template_name or news_type.value)
        
        # 3. 准备写作上下文
        writing_context = prepare_writing_context(
            original_content=original_content,
            ner_data=ner_data,
            label_data=label_data,
            event_data=event_data,
            analyst_data=analyst_data,
        )
        
        # 4. 调用LLM生成文章
        full_prompt = writing_prompt + "\n\n" + writing_context
        llm_output = self._call_llm(full_prompt)
        
        # 5. 解析LLM输出
        article_data = self._parse_llm_output(llm_output)
        
        # 6. 提取股票代码（从NER数据）
        stock_codes = self._extract_stocks(ner_data)
        
        # 7. 提取来源信息
        source = self._extract_source(event_data)
        
        # 8. 提取分类
        category_id, category_name = self._extract_category(label_data)
        
        # 9. 生成slug
        slug = self._generate_slug(article_data.get("title", ""), article_id)
        
        # 10. 组装文章
        now = datetime.now()
        
        # 解析情感和等级
        sentiment = self._parse_sentiment(article_data.get("sentiment", "neutral"))
        impact_level = self._parse_impact_level(article_data.get("impact_level", "medium"))
        
        article = Article(
            article_id=article_id,
            title=article_data.get("title", "财经新闻分析"),
            content=article_data.get("content", ""),
            publish_time=now,
            create_time=now,
            update_time=now,
            sub_title=article_data.get("sub_title"),
            summary=article_data.get("summary", ""),
            source=source,
            category_id=category_id,
            category_name=category_name,
            stock_codes=stock_codes,
            slug=slug,
            language=self.default_language,
            status=ArticleStatus.PUBLISHED,
            news_type=news_type,
            tags=article_data.get("tags", []),
            keywords=article_data.get("keywords", []),
            metadata=ArticleMetadata(
                sentiment=sentiment,
                impact_level=impact_level,
            ),
            # 保存原始分析数据用于追溯
            raw_data={"original_content": original_content},
            ner_data=ner_data,
            label_data=label_data,
            event_data=event_data,
            analyst_data=analyst_data,
        )
        
        return article
    
    def _call_llm(self, prompt: str) -> str:
        """
        调用LLM生成内容
        
        如果初始化时提供了llm_client则使用，否则使用默认的chat_once
        """
        if self.llm_client:
            return self.llm_client(prompt)
        else:
            # 使用默认的LLM调用
            try:
                from research.newsReader.llms import chat_once
                return chat_once(prompt)
            except ImportError:
                # 如果无法导入，返回一个默认的JSON格式输出
                return self._generate_fallback_output(prompt)
    
    def _generate_fallback_output(self, prompt: str) -> str:
        """当LLM不可用时生成默认输出"""
        # 从prompt中提取原始内容
        content_match = re.search(r'# 原始新闻内容\n\n(.+?)(?=\n---)', prompt, re.DOTALL)
        original_content = content_match.group(1).strip() if content_match else "暂无内容"
        
        # 生成默认JSON
        fallback = {
            "title": original_content[:30] + "..." if len(original_content) > 30 else original_content,
            "sub_title": "",
            "summary": original_content[:200] + "..." if len(original_content) > 200 else original_content,
            "content": f"# {original_content[:30]}\n\n{original_content}\n\n*（LLM服务暂时不可用，显示原始内容）*",
            "tags": [],
            "keywords": [],
            "sentiment": "neutral",
            "impact_level": "medium",
        }
        
        return json.dumps(fallback, ensure_ascii=False, indent=2)
    
    def _parse_llm_output(self, output: str) -> Dict[str, Any]:
        """
        解析LLM输出，提取JSON数据
        
        LLM可能输出：
        1. 纯JSON
        2. Markdown代码块包裹的JSON
        3. 带有说明文字的JSON
        """
        # 尝试直接解析
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取Markdown代码块中的JSON
        code_block_pattern = r'```(?:json)?\n(.*?)\n```'
        matches = re.findall(code_block_pattern, output, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # 尝试提取花括号中的内容
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # 如果都无法解析，尝试构造一个基本的返回
        return self._extract_fields_from_text(output)
    
    def _extract_fields_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取字段（备用方案）"""
        result = {
            "title": "",
            "sub_title": "",
            "summary": "",
            "content": text,
            "tags": [],
            "keywords": [],
            "sentiment": "neutral",
            "impact_level": "medium",
        }
        
        # 尝试提取标题（假设第一行是标题或包含"标题"）
        lines = text.split('\n')
        for line in lines[:10]:  # 检查前10行
            line = line.strip()
            if line.startswith('# ') or line.startswith('标题：') or line.startswith('标题:'):
                result["title"] = line.replace('# ', '').replace('标题：', '').replace('标题:', '').strip()
                break
            elif line and len(line) < 50 and not result["title"]:
                result["title"] = line
        
        # 尝试提取摘要
        if '摘要' in text:
            summary_match = re.search(r'摘要[：:]\s*(.+?)(?=\n\n|\n#|$)', text, re.DOTALL)
            if summary_match:
                result["summary"] = summary_match.group(1).strip()
        
        return result
    
    def _determine_news_type(
        self, 
        label_data: Dict[str, Any], 
        analyst_data: Dict[str, Any]
    ) -> NewsType:
        """根据标签和分析结果判断新闻类型"""
        classification = label_data.get("classification", {})
        news_types = classification.get("news_type", [])
        
        # 检查是否有深度分析的特征
        analyst_keys = [k.lower() for k in analyst_data.keys()]
        depth_indicators = ['fundamental', 'technical', 'valuation', 'macro']
        is_deep_analysis = any(ind in key for ind in depth_indicators for key in analyst_keys)
        
        if is_deep_analysis:
            return NewsType.ANALYSIS
        
        # 检查是否为研报类型
        for nt in news_types:
            label = nt.get("label", "") if isinstance(nt, dict) else nt
            if label in ["OPINION", "GUIDANCE", "RESEARCH"]:
                return NewsType.RESEARCH
        
        # 检查是否为快讯
        urgency = classification.get("urgency", {})
        if isinstance(urgency, dict):
            urgency_label = urgency.get("label", "")
            if urgency_label in ["P0_CRITICAL", "P1_HIGH"]:
                return NewsType.FLASH
        
        return NewsType.NEWS
    
    def _extract_stocks(self, ner_data: Dict[str, Any]) -> List[StockInfo]:
        """从NER数据提取股票代码"""
        stock_codes = []
        entities = ner_data.get("entities", [])
        
        seen = set()
        for entity in entities:
            if entity.get("type") in ["STOCK_CODE", "COMPANY"]:
                code = entity.get("stock_code", "")
                name = entity.get("normalized_name") or entity.get("text", "")
                
                if code and code not in seen:
                    seen.add(code)
                    stock_codes.append(StockInfo(
                        code=code,
                        name=name,
                    ))
        
        return stock_codes
    
    def _extract_source(self, event_data: Dict[str, Any]) -> Optional[SourceInfo]:
        """提取来源信息"""
        # 可以从event_data或其他数据源提取
        # 暂时返回None，可由外部设置
        return None
    
    def _extract_category(self, label_data: Dict[str, Any]) -> tuple:
        """提取分类信息"""
        classification = label_data.get("classification", {})
        news_types = classification.get("news_type", [])
        
        if news_types:
            if isinstance(news_types[0], dict):
                label = news_types[0].get("label", "NEWS")
            else:
                label = news_types[0]
            
            category_map = {
                "POLICY": ("policy", "政策"),
                "DATA_RELEASE": ("data", "数据"),
                "EVENT": ("event", "事件"),
                "EARNINGS": ("earnings", "财报"),
                "GUIDANCE": ("guidance", "指引"),
                "OPINION": ("opinion", "观点"),
            }
            
            return category_map.get(label, ("news", "新闻"))
        
        return ("news", "新闻")
    
    def _generate_slug(self, title: str, article_id: str) -> str:
        """生成SEO友好的slug"""
        # 简化处理：使用文章ID前8位
        return f"article-{article_id[:8]}"
    
    def _parse_sentiment(self, sentiment_str: str) -> Optional[Sentiment]:
        """解析情感字符串"""
        sentiment_map = {
            "positive": Sentiment.POSITIVE,
            "negative": Sentiment.NEGATIVE,
            "neutral": Sentiment.NEUTRAL,
            "mixed": Sentiment.MIXED,
        }
        return sentiment_map.get(sentiment_str.lower(), Sentiment.NEUTRAL)
    
    def _parse_impact_level(self, level_str: str) -> Optional[ImpactLevel]:
        """解析影响等级字符串"""
        level_map = {
            "high": ImpactLevel.HIGH,
            "medium": ImpactLevel.MEDIUM,
            "low": ImpactLevel.LOW,
        }
        return level_map.get(level_str.lower(), ImpactLevel.MEDIUM)


# 便捷函数
def write_report(
    article_id: str,
    original_content: str,
    ner_data: Dict[str, Any],
    label_data: Dict[str, Any],
    event_data: Dict[str, Any],
    analyst_data: Dict[str, Any],
    llm_client=None,
    **kwargs
) -> Article:
    """
    便捷函数：使用LLM生成报告
    
    Args:
        article_id: 文章ID
        original_content: 原始内容
        ner_data: NER结果
        label_data: 标签结果
        event_data: 事件结果
        analyst_data: 分析师结果
        llm_client: LLM客户端函数（可选）
        **kwargs: 其他参数
    
    Returns:
        Article对象
    """
    writer = ReportWriter(llm_client=llm_client)
    return writer.write(
        article_id=article_id,
        original_content=original_content,
        ner_data=ner_data,
        label_data=label_data,
        event_data=event_data,
        analyst_data=analyst_data,
        **kwargs
    )
