"""
/ghost 指令 - 查詢特定使用者的詐欺紀錄
"""
import discord
from discord import app_commands, Embed
from discord.app_commands import Choice
from discord.ext import commands


class GhostCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="ghost",
        description="查詢使用者的詐欺紀錄"
    )
    @app_commands.describe(
        user="目標使用者（不填則查詢自己）",
        public="是否公開顯示（預設僅自己可見）"
    )
    async def ghost(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        public: bool = False
    ):
        """
        查詢使用者的詐欺紀錄
        
        參數:
            user: 要查詢的使用者（選填，預設為自己）
            public: True = 所有人可見, False = 僅自己可見（預設）
        """
        target = user or interaction.user
        
        is_ephemeral = not public
        
        # 取得統計資料
        stats = await self.bot.repository.get_user_stats(user_id=target.id, guild_id=interaction.guild.id)
        
        # 沒有紀錄
        if not stats or stats.mention_count == 0:
            await interaction.response.send_message(f"📊 {target.mention} 還沒有詐欺紀錄！", ephemeral=is_ephemeral)
            return
        
        # 建立 Embed
        embed = Embed(
            title=f"👻 {target.display_name} 的詐欺紀錄",
            color=0xFF6B6B,
            description=f"統計時間: {stats.last_updated.strftime("%Y-%m-%d %H:%M") if stats.last_updated else "未知"}"
        )
        
        # 設定使用者頭像
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(
            name="👻 詐欺次數",
            value=f"**{stats.ghost_count}** 次",
            inline=True
        )
        
        # 被提及次數
        embed.add_field(
            name="📢 被提及次數",
            value=f"**{stats.mention_count}** 次",
            inline=True
        )
        
        # 回應率
        response_rate_pct = stats.response_rate * 100
        if response_rate_pct >= 80:
            rate_emoji = "🟢"
        elif response_rate_pct >= 50:
            rate_emoji = "🟡"
        else:
            rate_emoji = "🔴"
        
        embed.add_field(
            name="✅ 回應率",
            value=f"{rate_emoji} **{stats.response_rate:.1%}**",
            inline=True
        )
        
        # 顯示可見性提示
        if is_ephemeral:
            embed.set_footer(text="🔒 此訊息僅你可見")
        else:
            embed.set_footer(text=f"👀 由 {interaction.user.display_name} 公開查詢")
        
        # 發送訊息
        await interaction.response.send_message(
            embed=embed,
            ephemeral=is_ephemeral
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GhostCommand(bot))