"""
定義資料結構
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MentionRecord:
    """
    被 mention 的紀錄
    """
    id: Optional[int] = None
    guild_id: int = 0
    channel_id: int = 0
    message_id: int = 0
    mentioned_user_id: int = 0
    mentioner_user_id: int = 0
    mention_time: datetime = None
    responded: bool = False
    response_time: Optional[datetime] = None
    is_ghost: bool = False

@dataclass
class GhostStats:
    """
    使用者詐欺統計
    """
    user_id: int
    guild_id: int
    ghost_count: int = 0
    mention_count: int = 0
    response_rate: float = 0.0
    last_updated: datetime = None