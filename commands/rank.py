"""
/rank 指令 - 顯示詐欺排行榜
"""
import discord
from discord import app_commands, Embed
from typing import Literal
from discord.ext import commands


class RankCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="rank",
        description="查看詐欺排行榜"
    )
    @app_commands.describe(
        limit="顯示人數",
        public="是否公開顯示 (預設為 False，只有自己看得到)"
    )
    async def rank(
        self,
        interaction: discord.Interaction,
        limit: int = 10,
        public: bool = False
    ):
        limit = max(1, min(limit, 50))
        
        # 從資料庫取得排行榜
        stats = await self.bot.repository.get_leaderboard(
            guild_id=interaction.guild.id,
            limit=limit
        )
        
        # 如果沒有資料
        if not stats:
            await interaction.response.send_message(
                "📊 目前還沒有任何詐欺紀錄！大家都很守規矩呢 ✨",
                ephemeral=not public
            )
            return
        
        # 建立排行榜 Embed
        embed = Embed(
            title="👻 詐欺排行榜",
            description=f"顯示前 {len(stats)} 名詐欺慣犯",
            color=0xFF6B6B
        )
        
        # 獎牌 emoji
        medals = {
            1: "🥇",
            2: "🥈", 
            3: "🥉"
        }
        
        # 逐一添加排行
        for i, stat in enumerate(stats, start=1):
            # 取得使用者資訊
            try:
                user = self.bot.get_user(stat.user_id)
                if user is None:
                    user = await self.bot.fetch_user(stat.user_id)
                user_name = user.display_name
            except:
                # 如果使用者已離開伺服器或取得失敗
                user_name = f"未知使用者 ({stat.user_id})"
            
            # 排名顯示 (前三名加獎牌)
            rank_display = medals.get(i, f"{i}.")
            
            # 計算詐欺率
            ghost_rate = (stat.ghost_count / stat.mention_count * 100) if stat.mention_count > 0 else 0
            
            # 添加欄位
            embed.add_field(
                name=f"{rank_display} {user_name}",
                value=(
                    f"👻 詐欺: **{stat.ghost_count}** 次 ｜ "
                    f"📢 被提及: **{stat.mention_count}** 次 ｜ "
                    f"🚫 詐欺率: **{ghost_rate:.1f}%**"
                ),
                inline=False
            )
        
        # 添加統計摘要
        total_ghosts = sum(s.ghost_count for s in stats)
        total_mentions = sum(s.mention_count for s in stats)
        avg_response_rate = sum(s.response_rate for s in stats) / len(stats) if stats else 0
        
        embed.add_field(
            name="📊 本榜統計",
            value=(
                f"總詐欺數: **{total_ghosts}** 次\n"
                f"總提及數: **{total_mentions}** 次\n"
                f"平均回應率: **{avg_response_rate:.1%}**"
            ),
            inline=False
        )
        
        # 添加頁尾
        embed.set_footer(
            text=f"📅 {interaction.guild.name} • 共 {len(stats)} 人上榜"
        )
        
        # 發送訊息
        await interaction.response.send_message(
            embed=embed,
            ephemeral=not public
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RankCommand(bot))