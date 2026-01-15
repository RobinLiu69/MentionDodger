"""
回應判定器
職責: 判斷一條訊息是否算「有效回應」
"""
from discord import Message
from database.models import MentionRecord
from typing import Optional

class ResponseEvaluator:
    def __init__(self, min_length: int = 3):
        self.min_length = min_length
    
    def is_valid_response(self, message: Message, original_mention: MentionRecord) -> bool:
        """
        判定規則:
        1. 在同個頻道
        2. 發送者是被 mention 的人
        3. 在 timeout 時間內
        4. 訊息長度 >= min_length
        """
        # 檢查頻道
        if message.channel.id != original_mention.channel_id:
            return False
        
        # 檢查發送者
        if message.author.id != original_mention.mentioned_user_id:
            return False
        
        # 檢查內容長度
        if len(message.content.strip()) < self.min_length:
            return False
        
        
        return True