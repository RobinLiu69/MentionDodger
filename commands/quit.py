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
        description="退出詐欺排行榜追蹤"
    )
    @app_commands.describe(
        keep_stats="是否保留歷史統計資料（預設保留）"
    )
    async def quit(
        self,
        interaction: discord.Interaction,
        keep_stats: bool = True
    ):
        """
        退出追蹤名單
        
        參數:
            keep_stats: True = 保留統計資料, False = 清除所有紀錄
        """
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # 檢查是否在追蹤中
        is_tracked = await self.bot.repository.is_player_tracked(user_id, guild_id)
        
        if not is_tracked:
            # 不在名單中
            embed = Embed(
                title="⚠️ 你不在追蹤名單中",
                description=f"{interaction.user.mention} 你目前沒有被追蹤",
                color=0xFFA500
            )
            embed.add_field(
                name="💡 提示",
                value="使用 `/join` 指令可以加入追蹤",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 取得當前統計資料
        stats = await self.bot.repository.get_user_stats(user_id, guild_id)
        
        # 移出追蹤名單
        success = await self.bot.repository.remove_player(user_id, guild_id)
        
        if success:
            embed = Embed(
                title="👋 已退出追蹤名單",
                description=f"{interaction.user.mention} 已成功退出詐欺追蹤",
                color=0x00BFFF
            )
            
            # 顯示統計摘要
            if stats and stats.mention_count > 0:
                embed.add_field(
                    name="📊 你的最終統計",
                    value=(
                        f"• 被提及次數: **{stats.mention_count}** 次\n"
                        f"• 詐欺次數: **{stats.ghost_count}** 次\n"
                        f"• 回應率: **{stats.response_rate:.1%}**"
                    ),
                    inline=False
                )
            
            # 根據是否保留統計顯示不同訊息
            if keep_stats:
                embed.add_field(
                    name="💾 資料保留",
                    value="你的歷史統計已保留，重新加入後可繼續累積",
                    inline=False
                )
            else:
                # 清除統計
                await self.bot.repository.reset_user_stats(user_id, guild_id)
                embed.add_field(
                    name="🗑️ 資料已清除",
                    value="所有歷史紀錄已刪除，重新加入將從零開始",
                    inline=False
                )
            
            embed.add_field(
                name="🔄 重新加入",
                value="隨時可以使用 `/join` 重新加入追蹤",
                inline=False
            )
            
            embed.set_footer(text=f"退出時間: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
        else:
            # 移出失敗（理論上不應該發生）
            embed = Embed(
                title="❌ 退出失敗",
                description="發生未知錯誤，請稍後再試或聯繫管理員",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuitCommand(bot))