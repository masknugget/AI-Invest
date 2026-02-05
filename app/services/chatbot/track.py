from datetime import datetime
from typing import Optional, List, Dict, Any


class ChatTracker:
    def __init__(self):
        self.user_id: Optional[str] = None
        self.chat_id: Optional[str] = None
        self.messages: Optional[List[Dict[str, Any]]] = None
        self.conversation_id: Optional[str] = None
        self.user_query: Optional[str] = None
        self.content: str = ""
        self.create_datetime: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stock_symbol: Optional[str] = None
        self.model: Optional[str] = None
        self.tokens_used: Optional[int] = None

    def add_content(self, content: str):
        """
        添加信息
        """
        self.content += content

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "conversation_id": self.conversation_id,
            "messages": [
                {"role": "user", "content": self.user_query},
                {"role": "assistant", "content": self.content}
            ],
            "user_query": self.user_query,
            "content": self.content,
            "create_datetime": self.create_datetime,
            "stock_symbol": self.stock_symbol,
            "model": self.model,
            "tokens_used": self.tokens_used,
        }

