"""
Bot 啟動事件
"""
from discord.ext import commands

class ReadyEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ {self.bot.user} 已上線!")
        print(f"📊 已加入 {len(self.bot.guilds)} 個伺服器")

async def setup(bot):
    await bot.add_cog(ReadyEvents(bot))