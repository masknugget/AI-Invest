import json

from recommender.newsReader.agents.analyst.symbol import prompt_technical, prompt_fundamental, prompt_high_dividend, \
    prompt_highlow52
from recommender.newsReader.agents.reporter.align_data import prompt_align_data
from recommender.newsReader.llms import chat_once
from recommender.newsReader.utils import parse_json_from_llm


def pipeline_symbols(
        symbols: str
) -> dict:
    p_tech = prompt_technical()
    p_fund = prompt_fundamental()
    p_high = prompt_high_dividend()
    p_highlow = prompt_highlow52()

    data_tech = chat_once(p_tech)
    data_fund = chat_once(p_fund)
    data_high = chat_once(p_high)
    data_highlow = chat_once(p_highlow)

    align_tech = prompt_align_data(json.dumps({"data": data_tech}))
    align_fund = prompt_align_data(json.dumps({"data": data_fund}))
    align_high = prompt_align_data(json.dumps({"data": data_high}))
    align_highlow = prompt_align_data(json.dumps({"data": data_highlow}))

    align_tech = chat_once(align_tech)
    align_fund = chat_once(align_fund)
    align_high = chat_once(align_high)
    align_highlow = chat_once(align_highlow)

    align_tech = parse_json_from_llm(align_tech)
    align_fund = parse_json_from_llm(align_fund)
    align_high = parse_json_from_llm(align_high)
    align_highlow = parse_json_from_llm(align_highlow)

    return {
        "tech": align_tech,
        "fund": align_fund,
        "high": align_high,
        "highlow": align_highlow,
    }
