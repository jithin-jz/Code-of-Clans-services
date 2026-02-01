from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, JSON
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

def get_ist_time():
    return datetime.now(ZoneInfo("Asia/Kolkata"))

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room: str = Field(index=True)
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    message: str
    timestamp: datetime = Field(
        default_factory=get_ist_time,
        sa_column=Column(DateTime(timezone=True))
    )
    reactions: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # {emoji: [usernames]}
