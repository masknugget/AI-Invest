import time
import urllib.parse
from pymongo import MongoClient
from app.config.config import Config

__client = None


def _get_init_db():
    user = Config.user
    host = Config.host
    db = Config.db
    ca = Config.ca
    pwd = Config.pwd
    uri = f"mongodb://{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pwd)}@{host}:27017/{db}?replicaSet=rs0&readPreference=secondary"

    kwargs = dict(
        tlsAllowInvalidHostnames=True,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000,
        socketTimeoutMS=15000,
        waitQueueTimeoutMS=15000,
        maxPoolSize=50
    )
    if ca is not None:
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = ca

    client = MongoClient(uri, **kwargs)
    print("初始化client成功")
    return client


def _init_db():
    global __client
    if __client is None:
        __client = _get_init_db()
    elif __client._closed:
        __client = _get_init_db()
    return __client, __client[Config.db]
