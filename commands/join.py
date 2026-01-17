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
        description="自願加入詐欺排行榜追蹤"
    )
    async def join(
        self,
        interaction: discord.Interaction
    ):
        """
        加入追蹤名單
        只有在名單中的玩家，其 mention 行為才會被追蹤
        """
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # 檢查是否已在追蹤中
        is_tracked = await self.bot.repository.is_player_tracked(user_id, guild_id)
        
        if is_tracked:
            # 已經在名單中
            embed = Embed(
                title="⚠️ 已在追蹤名單中",
                description=f"{interaction.user.mention} 你已經在詐欺追蹤名單中了！",
                color=0xFFA500
            )
            embed.add_field(
                name="💡 提示",
                value="使用 `/quit` 指令可以退出追蹤",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 加入追蹤名單
        success = await self.bot.repository.add_player(user_id, guild_id)
        
        if success:
            # 成功加入
            embed = Embed(
                title="✅ 成功加入追蹤名單",
                description=f"歡迎 {interaction.user.mention} 加入詐欺排行榜！",
                color=0x00FF00
            )
            embed.add_field(
                name="📊 追蹤規則",
                value=(
                    "• 當你被 @ 提及時，系統會開始計時\n"
                    f"• 你需要在 {self.bot.config['ghost_rules']['response_timeout']} 秒內回應\n"
                    "• 超時未回應將被記錄為詐欺\n"
                    "• 使用 `/ghost` 查看自己的統計\n"
                    "• 使用 `/rank` 查看排行榜"
                ),
                inline=False
            )
            embed.add_field(
                name="🚪 退出方式",
                value="隨時可以使用 `/quit` 退出追蹤",
                inline=False
            )
            embed.set_footer(text=f"加入時間: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
        else:
            # 加入失敗
            embed = Embed(
                title="❌ 加入失敗",
                description="發生未知錯誤，請稍後再試或聯繫管理員",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(JoinCommand(bot))