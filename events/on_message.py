"""
訊息事件監聽
職責:
1. 偵測新訊息是否包含 mention → 建立追蹤
2. 偵測新訊息是否為回應 → 取消 timeout
"""
from datetime import datetime, timedelta
from discord.ext import commands
from discord import Message
from core.tracker import MentionTracker
from core.evaluator import ResponseEvaluator
from core.scheduler import TimeoutScheduler

class MessageEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 從 bot 取得初始化好的元件
        self.tracker: MentionTracker = bot.tracker
        self.evaluator: ResponseEvaluator = bot.evaluator
        self.scheduler: TimeoutScheduler = bot.scheduler
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return
        
        if message.content.startswith("/"):
            return
        

        # 這邊之後會整合到 tracker.py
        # 1. 檢查是否有新的 mention
        if message.mentions:
            records = await self.tracker.track_mentions(message)
            for record in records:
                self.scheduler.schedule_timeout(record)
        
        # 2. 檢查是否回應了之前的 mention
        pending = await self.bot.repository.get_pending_mentions(
            user_id=message.author.id,
            channel_id=message.channel.id
        )
        
        for mention_record in pending:
            if self.evaluator.is_valid_response(message, mention_record):
                await self.bot.repository.mark_as_responded(mention_record.id, datetime.now())
                self.scheduler.cancel_timeout(mention_record.id)

async def setup(bot):
    await bot.add_cog(MessageEvents(bot))