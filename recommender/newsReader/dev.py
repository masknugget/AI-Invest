from research.newsReader.agents.analyst.factory import create_analyst
from research.newsReader.agents.pipelines.event import prompt_event
from research.newsReader.agents.pipelines.labels import prompt_labels
from research.newsReader.agents.pipelines.ner import prompt_ner
from research.newsReader.agents.pipelines.router import prompt_router
from research.newsReader.agents.reporter import ReportWriter, Article
from research.newsReader.llms import chat_once
from research.newsReader.utils import parse_json_from_llm, gen_uuid


def analyst(content):
    """
    完整的财经新闻分析流程
    
    流程：
    1. NER实体识别
    2. 标签分类
    3. 事件结构化
    4. 路由决策
    5. 调用对应analyst进行分析
    6. 使用reporter生成标准格式文章
    
    Args:
        content: 原始新闻内容
    
    Returns:
        包含完整文章和分析数据的字典
    """
    # 生成唯一ID
    article_id = gen_uuid()
    
    # Step 1: 基础信息提取
    p_ner = prompt_ner()
    p_labels = prompt_labels()
    p_event = prompt_event()

    out_data = {
        "article_id": article_id,
        "content": content,
    }

    content_str = f"""
# 新闻内容
{content}
"""

    # 调用LLM进行基础分析
    out_ner = chat_once(p_ner + content_str)
    out_label = chat_once(p_labels + content_str)
    out_event = chat_once(p_event + content_str)

    # Step 2: 路由决策
    p_router = prompt_router()

    p_data = f"""
# 新闻内容
{content}

# ner
{out_ner}

# label
{out_label}

# event
{out_event}

"""

    out_router = chat_once(p_data + p_router)
    out_router_json = parse_json_from_llm(out_router)

    primary_agents = out_router_json.get('routing_plan', {}).get('primary_agents', [])
    primary_agents = [i.get('agent') for i in primary_agents]

    # Step 3: 调用对应analyst
    data_analyst = {}
    for name in primary_agents:
        p_analyst, p_name = create_analyst(name)
        out_analyst = chat_once(p_data + p_analyst)
        data_analyst[p_name] = out_analyst
        out_data[name] = out_analyst

    # 解析所有JSON数据
    data_ner = parse_json_from_llm(out_ner)
    data_label = parse_json_from_llm(out_label)
    data_event = parse_json_from_llm(out_event)
    data_router = parse_json_from_llm(out_router)

    # Step 4: 使用Reporter生成标准文章
    writer = ReportWriter()
    
    article = writer.write(
        article_id=article_id,
        original_content=content,
        ner_data=data_ner,
        label_data=data_label,
        event_data=data_event,
        analyst_data=data_analyst,
    )
    
    # 转换为字典格式
    article_dict = article.to_dict()

    # 组装输出数据
    out_data['data_ner'] = data_ner
    out_data['data_label'] = data_label
    out_data['data_event'] = data_event
    out_data['data_router'] = data_router
    out_data['data_analyst'] = data_analyst
    out_data['article'] = article_dict  # 完整的标准文章
    
    # 保留原来的字段兼容
    out_data['data_report'] = article.content
    out_data['uuid'] = article_id
    out_data['title'] = article.title
    out_data['summary'] = article.summary

    return out_data


def analyst_with_report(content, template_name=None):
    """
    带指定模板的分析流程
    
    Args:
        content: 原始新闻内容
        template_name: 指定模板名称 (flash/news/analysis/research)
    
    Returns:
        包含完整文章和分析数据的字典
    """
    article_id = gen_uuid()
    
    # 基础分析
    p_ner = prompt_ner()
    p_labels = prompt_labels()
    p_event = prompt_event()

    content_str = f"# 新闻内容\n{content}"
    
    out_ner = chat_once(p_ner + content_str)
    out_label = chat_once(p_labels + content_str)
    out_event = chat_once(p_event + content_str)

    # 路由和分析师调用
    p_router = prompt_router()
    p_data = f"{content_str}\n\n# ner\n{out_ner}\n\n# label\n{out_label}\n\n# event\n{out_event}\n"
    out_router = chat_once(p_data + p_router)
    out_router_json = parse_json_from_llm(out_router)

    primary_agents = out_router_json.get('routing_plan', {}).get('primary_agents', [])
    primary_agents = [i.get('agent') for i in primary_agents]

    data_analyst = {}
    for name in primary_agents:
        p_analyst, p_name = create_analyst(name)
        out_analyst = chat_once(p_data + p_analyst)
        data_analyst[p_name] = out_analyst

    # 解析数据
    data_ner = parse_json_from_llm(out_ner)
    data_label = parse_json_from_llm(out_label)
    data_event = parse_json_from_llm(out_event)

    # 使用指定模板生成文章
    writer = ReportWriter()
    article = writer.write(
        article_id=article_id,
        original_content=content,
        ner_data=data_ner,
        label_data=data_label,
        event_data=data_event,
        analyst_data=data_analyst,
        template_name=template_name,
    )

    return {
        "article_id": article_id,
        "article": article.to_dict(),
        "analysis": {
            "ner": data_ner,
            "labels": data_label,
            "event": data_event,
            "router": out_router_json,
            "analysts": data_analyst,
        }
    }
