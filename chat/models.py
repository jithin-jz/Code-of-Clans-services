from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room: str = Field(index=True)
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
