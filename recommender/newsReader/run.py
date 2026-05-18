import json
import os

import pandas as pd

from research.newsReader.agents.pipelines.event import prompt_event
from research.newsReader.agents.pipelines.labels import prompt_labels
from research.newsReader.agents.pipelines.ner import prompt_ner
from research.newsReader.agents.pipelines.router import prompt_router
from research.newsReader.agents.report import prompt_report
from research.newsReader.dev import analyst
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

def save_dict(data, filename):
    """将 dict 保存为 JSON 文件"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_dict(filename):
    """从 JSON 文件读取 dict"""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


cnt = 0
for i in news:
    cnt += 1
    print(cnt)
    try:
        file_path = rf"F:\work\\report\\{cnt}.json"
        out_data = analyst(i)
        save_dict(out_data, file_path)

    except Exception as e:
        print(e)
        continue

