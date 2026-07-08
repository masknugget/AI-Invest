import json
import uuid

from typing import TypeVar, Dict, Any

from json_repair import repair_json
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

T = TypeVar("T", bound=Dict[str, Any])


def gen_uuid():
    """生成随机 UUID4，返回带横杠的字符串"""
    return str(uuid.uuid4())


def parse_json_from_llm(content: str) -> T:
    """
    从 LLM 返回的文本中解析出 JSON 对象。

    参数
    ----
    content : str
        大模型返回的原始字符串，通常包含一个 ```json ... ``` 代码块。

    返回
    ----
    T
        解析后的 JSON 字典（键值均为 str / Any）。

    异常
    ----
    OutputParserException
        如果无法找到或解析出合法 JSON。
    """
    parser = JsonOutputParser()

    try:
        content = repair_json(content)
    except OutputParserException as e:
        print("repair_json fail")

    try:
        # 使用 LangChain 提供的 JsonOutputParser 提取并解析 JSON
        parsed: T = parser.parse(content)
        return parsed
    except OutputParserException as e:
        # 将底层异常信息包装后再次抛出，方便上游统一处理
        # raise OutputParserException(f"无法从 LLM 返回中提取 JSON：{e}") from e
        print("json_parse错误，")
        pass

    try:
        data = json.loads(content)
        return data
    except json.decoder.JSONDecodeError as e:
        print("json load错误")

    try:
        data = eval(content)
        return data
    except Exception as e:
        raise e
