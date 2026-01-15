"""
Mention 追蹤核心
職責:
1. 偵測訊息中的 @mention
2. 建立追蹤任務
3. 與 scheduler 協作設定 timeout
"""
from discord import Message, Member
from typing import List
from database.repository import GhostRepository
from database.models import MentionRecord
from datetime import datetime

class MentionTracker:
    def __init__(self, repository: GhostRepository, timeout: int):
        self.repo = repository
        self.timeout = timeout  # 從 config 讀取
    
    async def track_mentions(self, message: Message) -> List[MentionRecord]:
        """
        從訊息中提取所有 mention 並建立追蹤
        """
        records = []
        for mentioned in message.mentions:
            if mentioned.bot:  # 忽略 bot
                continue
            
            record = MentionRecord(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                mentioned_user_id=mentioned.id,
                mentioner_user_id=message.author.id,
                mention_time=datetime.now(),
                responded=False
            )
            
            record_id = await self.repo.add_mention(record)
            record.id = record_id
            records.append(record)
        
        return records
    
    async def check_for_response(self, message: Message):
        """
        檢查這條訊息是否回應了之前的 mention
        呼叫 evaluator 判斷
        """
        # 目前被on_message搶走 下次修