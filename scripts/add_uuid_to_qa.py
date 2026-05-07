#!/usr/bin/env python3
"""
为 stock_qa_5000.json 中的每条记录添加 UUID，生成 data_qa_5000.json
"""

import json
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，以便导入 app.utils.gen_uuid
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.gen_uuid import generate_uuid_str


def main():
    input_path = PROJECT_ROOT / "scripts" / "data_local" / "stock_qa_5000.json"
    output_path = PROJECT_ROOT / "scripts" / "data_local" / "data_qa_5000.json"

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    new_data = []
    for item in data:
        new_item = {
            "uuid": generate_uuid_str(),
            "meta_data": item["meta_data"],
            "query": item["query"],
            "answer": item["answer"],
        }
        new_data.append(new_item)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"已处理 {len(new_data)} 条记录")
    print(f"输出文件: {output_path}")


if __name__ == "__main__":
    main()
