import os

import pandas as pd

from research.newsReader.agents.analyst.factory import create_analyst
from research.newsReader.agents.pipelines.event import prompt_event
from research.newsReader.agents.pipelines.labels import prompt_labels
from research.newsReader.agents.pipelines.ner import prompt_ner
from research.newsReader.agents.pipelines.router import prompt_router
from research.newsReader.agents.report import prompt_report
from research.newsReader.llms import chat_once
from research.newsReader.utils import parse_json_from_llm

dir_path = r'D:\BaiduNetdiskDownload\财经新闻\新浪财经新闻-2025'

file_names = os.listdir(dir_path)

news = []
for i in file_names:
    file_path = os.path.join(dir_path, i)

    df = pd.read_csv(file_path, encoding='gbk')
    content = df.content.to_list()
    news.extend(content)

    if len(news) >= 3000:
        break




content = news[100]
p_ner = prompt_ner()
p_labels = prompt_labels()
p_event = prompt_event()

content_str = f"""
# 新闻内容
{content}
"""

out_ner = chat_once(p_ner + content_str)
out_label = chat_once(p_labels + content_str)
out_event = chat_once(p_event + content_str)

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


out_data = {}
data_analyst = {}
for name in primary_agents:
    p_analyst, p_name = create_analyst(name)

    out_analyst = chat_once(p_data + p_analyst)
    data_analyst[p_name] = out_analyst
    out_data[name] = out_analyst


data_ner = parse_json_from_llm(out_ner)
data_label = parse_json_from_llm(out_label)
data_event = parse_json_from_llm(out_event)
data_router = parse_json_from_llm(out_router)

out_data['data_ner'] = data_ner
out_data['data_label'] = data_label
out_data['data_event'] = data_event
out_data['data_router'] = data_router


p_report = prompt_report()

content = ["#" + k + "\n" + v for k, v in data_analyst.items()]

data = content_str + p_report + content[0]

report  = chat_once(data)


out_data['data_report'] = report
