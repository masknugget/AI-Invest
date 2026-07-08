# 如果其他文件是 `from db import get_chat_history` 这种用法
from app.core.db.connection import _init_db
from app.core.db.chat_history import *
from app.core.db.user_profile import *
from app.core.db.recommendation import *
from app.core.db.insight import *
from app.core.db.stock_data import *
from app.core.db.stock_news import *
from app.core.db.p_advisor import *
