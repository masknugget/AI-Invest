from recommender.news_reader.llms import chat_once

def reason_llm(
        code_in,
        dimension_in,
        code_out,
        dimension_out,
) -> str:
    out_data = f"""
    
    # 任务
    正在进行一次股票调仓，分析调入调出的差异和理由
    
    # 输出格式
    以json格式进行输出
    
    {{
        "reason": ***
    }}
    
    ## 调入
    {code_in}
    
    {dimension_in}
    ## 调出
    {code_out}
    
    {dimension_out}
    
    """

    result = chat_once(out_data)
    return result
