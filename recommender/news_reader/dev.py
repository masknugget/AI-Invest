import json
import os

import pandas as pd

from app.core.database import get_mongo_db_sync
from recommender.news_reader.agents.analyst.factory import create_analyst
from recommender.news_reader.agents.pipelines.event import prompt_event
from recommender.news_reader.agents.pipelines.labels import prompt_labels
from recommender.news_reader.agents.pipelines.ner import prompt_ner
from recommender.news_reader.agents.pipelines.router import prompt_router
from recommender.news_reader.agents.report import prompt_report
from recommender.news_reader.agents.reporter.align_data import prompt_align_data
from recommender.news_reader.consumer.news import pipeline_news
from recommender.news_reader.llms import chat_once
from recommender.news_reader.utils import parse_json_from_llm

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


cnt = 0
for content in news[500:]:
    cnt += 1
    print(cnt, "<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>")
    try:
        data_news = pipeline_news(content)

        db = get_mongo_db_sync()
        collection = db["insight_agg"]

        collection.insert_one(data_news)
    except Exception as e:
        print(e)
        continue
