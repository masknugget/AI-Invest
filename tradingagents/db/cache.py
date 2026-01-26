from cachetools import TTLCache

# 参数：maxsize=最大条目数，ttl=过期时间（秒）
cache = TTLCache(maxsize=100, ttl=25)
