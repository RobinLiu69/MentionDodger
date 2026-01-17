"""
Mention 追蹤核心
職責:
1. 偵測訊息中的 @mention
2. 建立追蹤任務（僅追蹤名單中的玩家）
3. 與 scheduler 協作設定 timeout
"""
from discord import Message, Member
from typing import List
from database.repository import GhostRepository
from database.models import MentionRecord
from datetime import datetime
import logging

logger = logging.getLogger("MentionDodger.Tracker")

class MentionTracker:
    def __init__(self, repository: GhostRepository, timeout: int):
        self.repo = repository
        self.timeout = timeout
    
    async def track_mentions(self, message: Message) -> List[MentionRecord]:
        """
        從訊息中提取所有 mention 並建立追蹤
        只追蹤在名單中的玩家
        """
        records = []
        
        for mentioned in message.mentions:
            # 忽略 bot
            if mentioned.bot:
                logger.debug(f"忽略 bot mention: {mentioned.id}")
                continue
            
            # 檢查是否在追蹤名單中
            is_tracked = await self.repo.is_player_tracked(
                user_id=mentioned.id,
                guild_id=message.guild.id
            )
            
            if not is_tracked:
                logger.debug(f"使用者 {mentioned.id} 不在追蹤名單中，跳過")
                continue
            
            # 建立追蹤紀錄
            record = MentionRecord(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                mentioned_user_id=mentioned.id,
                mentioner_user_id=message.author.id,
                mention_time=datetime.now(),
                responded=False
            )
            
            # 儲存到資料庫
            record_id = await self.repo.add_mention(record)
            record.id = record_id
            records.append(record)
            
            logger.info(
                f"建立 mention 追蹤: user={mentioned.id}, "
                f"channel={message.channel.id}, record_id={record_id}"
            )
        
        return records
    
    async def check_for_response(self, message: Message):
        """
        檢查這條訊息是否回應了之前的 mention
        呼叫 evaluator 判斷
        """
        # 目前被 on_message 搶走，下次修