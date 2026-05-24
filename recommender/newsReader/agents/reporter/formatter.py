"""
文章格式化工具

提供文章内容的格式化、清洗、摘要生成等功能
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime


def format_article_content(content: str, format_type: str = "markdown") -> str:
    """
    格式化文章内容
    
    Args:
        content: 原始内容
        format_type: 格式类型 (markdown/html/plain)
    
    Returns:
        格式化后的内容
    """
    if format_type == "markdown":
        return _format_markdown(content)
    elif format_type == "html":
        return _format_html(content)
    elif format_type == "plain":
        return _format_plain(content)
    else:
        return content


def _format_markdown(content: str) -> str:
    """格式化为标准Markdown"""
    # 规范化标题层级
    content = _normalize_headers(content)
    
    # 规范化列表
    content = _normalize_lists(content)
    
    # 规范化表格
    content = _normalize_tables(content)
    
    # 清理多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()


def _format_html(content: str) -> str:
    """转换为HTML格式"""
    # 简单转换，实际项目可以使用markdown库
    html = content
    
    # 转换标题
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    
    # 转换粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # 转换斜体
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # 转换换行
    html = html.replace('\n\n', '</p><p>')
    html = '<p>' + html + '</p>'
    
    return html


def _format_plain(content: str) -> str:
    """转换为纯文本"""
    # 移除Markdown标记
    plain = content
    plain = re.sub(r'#+ ', '', plain)  # 标题
    plain = re.sub(r'\*\*', '', plain)  # 粗体
    plain = re.sub(r'\*', '', plain)  # 斜体/列表
    plain = re.sub(r'`', '', plain)  # 代码
    plain = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', plain)  # 链接
    
    return plain.strip()


def _normalize_headers(content: str) -> str:
    """规范化标题层级"""
    lines = content.split('\n')
    result = []
    
    for line in lines:
        # 检测ATX风格标题
        match = re.match(r'^(#{1,6})\s*(.+)$', line)
        if match:
            hashes, title = match.groups()
            result.append(f"{hashes} {title.strip()}")
        else:
            result.append(line)
    
    return '\n'.join(result)


def _normalize_lists(content: str) -> str:
    """规范化列表"""
    lines = content.split('\n')
    result = []
    
    for line in lines:
        # 规范化无序列表
        line = re.sub(r'^[\*\+\-]\s*', '- ', line)
        # 规范化有序列表
        line = re.sub(r'^(\d+)[\.\)]\s*', r'\1. ', line)
        result.append(line)
    
    return '\n'.join(result)


def _normalize_tables(content: str) -> str:
    """规范化表格"""
    # 简化处理，确保表格格式正确
    return content


def generate_summary(content: str, max_length: int = 300) -> str:
    """
    生成内容摘要
    
    Args:
        content: 文章内容
        max_length: 最大长度
    
    Returns:
        摘要文本
    """
    # 移除Markdown标记
    plain_text = _format_plain(content)
    
    # 按句子分割
    sentences = re.split(r'[。！？\n]', plain_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    
    if not sentences:
        return plain_text[:max_length] + "..." if len(plain_text) > max_length else plain_text
    
    # 选取前几个完整句子
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) < max_length:
            summary += sentence + "。"
        else:
            break
    
    return summary


def generate_title(
    content: str, 
    entities: List[Dict[str, Any]], 
    max_length: int = 50
) -> str:
    """
    生成文章标题
    
    Args:
        content: 文章内容
        entities: 实体列表
        max_length: 最大长度
    
    Returns:
        标题文本
    """
    # 尝试提取公司名
    companies = [e for e in entities if e.get("type") == "COMPANY"]
    
    if companies:
        company_name = companies[0].get("normalized_name") or companies[0].get("text", "")
        
        # 提取关键事件
        events = [e for e in entities if e.get("type") and e.get("type").startswith("EVENT_")]
        if events:
            event_type = events[0].get("type", "").replace("EVENT_", "")
            title = f"{company_name}{event_type}"
        else:
            # 从内容提取关键词
            keywords = extract_keywords(content, top_k=3)
            title = f"{company_name}：{' '.join(keywords)}"
        
        if len(title) <= max_length:
            return title
    
    # 备用方案：使用内容前N个字
    plain_content = _format_plain(content)
    first_line = plain_content.split('\n')[0] if plain_content else ""
    
    if len(first_line) > max_length:
        return first_line[:max_length] + "..."
    
    return first_line or "财经新闻"


def extract_keywords(content: str, top_k: int = 5) -> List[str]:
    """
    提取关键词
    
    Args:
        content: 文章内容
        top_k: 返回前K个关键词
    
    Returns:
        关键词列表
    """
    # 简单的关键词提取，实际项目可以使用jieba等分词工具
    # 这里使用简单的规则：提取名词性短语和停用词过滤
    
    # 金融相关停用词
    stopwords = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也',
        '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
        '公司', '表示', '认为', '进行', '完成', '实现', '达到', '预计', '根据', '关于'
    }
    
    # 移除Markdown标记
    plain_text = _format_plain(content)
    
    # 简单分词（按字符和常见分隔符）
    words = re.findall(r'[\u4e00-\u9fa5]{2,8}', plain_text)
    
    # 统计词频
    word_freq = {}
    for word in words:
        if word not in stopwords and len(word) >= 2:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # 返回高频词
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:top_k]]


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """格式化日期时间"""
    return dt.strftime(format_str)


def generate_slug(title: str, article_id: str) -> str:
    """
    生成SEO友好的URL slug
    
    Args:
        title: 文章标题
        article_id: 文章ID
    
    Returns:
        slug字符串
    """
    # 简化处理：使用文章ID前8位
    return f"news-{article_id[:8]}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀
    
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def clean_html_tags(text: str) -> str:
    """清理HTML标签"""
    return re.sub(r'<[^>]+>', '', text)


def word_count(content: str) -> int:
    """
    统计字数
    
    Args:
        content: 内容
    
    Returns:
        字数
    """
    # 移除空白字符后统计
    plain_text = _format_plain(content)
    # 中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', plain_text))
    # 英文单词
    english_words = len(re.findall(r'[a-zA-Z]+', plain_text))
    
    return chinese_chars + english_words


def reading_time(content: str, wpm: int = 300) -> int:
    """
    估算阅读时间
    
    Args:
        content: 内容
        wpm: 每分钟阅读字数（中文约300字）
    
    Returns:
        阅读时间（分钟）
    """
    count = word_count(content)
    return max(1, round(count / wpm))


class ContentValidator:
    """内容验证器"""
    
    @staticmethod
    def validate_required_fields(article: Dict[str, Any]) -> List[str]:
        """验证必需字段"""
        errors = []
        
        required = ["article_id", "title", "content", "publish_time", "create_time"]
        for field in required:
            if not article.get(field):
                errors.append(f"缺少必需字段: {field}")
        
        return errors
    
    @staticmethod
    def validate_content_quality(content: str) -> Dict[str, Any]:
        """验证内容质量"""
        issues = []
        score = 100
        
        # 检查内容长度
        if len(content) < 100:
            issues.append("内容过短")
            score -= 20
        
        # 检查空段落
        empty_paragraphs = len(re.findall(r'\n\s*\n', content))
        if empty_paragraphs > 5:
            issues.append("存在过多空段落")
            score -= 10
        
        # 检查重复内容
        sentences = content.split('。')
        unique_sentences = set(sentences)
        if len(sentences) != len(unique_sentences):
            issues.append("存在重复句子")
            score -= 15
        
        # 检查格式
        if content.count('#') == 0 and len(content) > 500:
            issues.append("长内容缺少标题层级")
            score -= 10
        
        return {
            "score": max(0, score),
            "issues": issues,
            "is_valid": score >= 60
        }


def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    # 移除非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 限制长度
    if len(filename) > 100:
        filename = filename[:100]
    return filename.strip()


def extract_stock_codes(text: str) -> List[str]:
    """
    从文本中提取股票代码
    
    Args:
        text: 文本内容
    
    Returns:
        股票代码列表
    """
    # A股代码模式
    a_share_pattern = r'\b(6\d{5}|0\d{5}|3\d{5}|8\d{5}|4\d{5})(\.SH|\.SZ|\.BJ)?\b'
    # 港股代码模式
    hk_pattern = r'\b(\d{4,5})\.HK\b'
    # 美股代码模式（大写字母）
    us_pattern = r'\b([A-Z]{1,5})\b'
    
    codes = []
    
    # 提取A股
    for match in re.finditer(a_share_pattern, text):
        codes.append(match.group(0))
    
    # 提取港股
    for match in re.finditer(hk_pattern, text):
        codes.append(match.group(0))
    
    return list(set(codes))
