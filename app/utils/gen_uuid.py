import uuid


def generate_uuid_str(with_hyphens: bool = False) -> str:
    """生成字符串 UUID，可选择是否保留连字符"""
    uid = uuid.uuid4()
    if with_hyphens:
        return str(uid)
    return uid.hex
