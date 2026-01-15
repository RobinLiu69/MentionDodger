"""
/join 指令 - 加入追蹤名單
"""
import discord
from discord import app_commands, Embed
from discord.ext import commands


class JoinCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="join",
        description="自願加入詐欺排行榜"
    )
    async def join(
        self,
        interaction: discord.Interaction
    ):
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(JoinCommand(bot))