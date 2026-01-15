"""
/quit 指令 - 退出追蹤名單
"""
import discord
from discord import app_commands, Embed
from discord.ext import commands


class QuitCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="quit",
        description="退出詐欺排行榜"
    )
    async def quit(
        self,
        interaction: discord.Interaction
    ):
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(QuitCommand(bot))