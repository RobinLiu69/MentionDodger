"""
/config 指令 - 系統設定與查詢
"""
import discord
from discord import app_commands, Embed
from discord.ext import commands
from typing import Optional, Literal
import yaml
import os


class ConfigCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # 主指令群組
    config_group = app_commands.Group(
        name="config",
        description="系統設定與查詢"
    )
    
    @config_group.command(
        name="list",
        description="查看目前追蹤中的玩家名單"
    )
    @app_commands.describe(
        public="是否公開顯示（預設僅自己可見）"
    )
    async def list_players(
        self,
        interaction: discord.Interaction,
        public: bool = False
    ):
        """
        顯示目前在追蹤名單中的所有玩家
        """
        guild_id = interaction.guild.id
        
        # 取得所有被追蹤的玩家
        tracked_players = await self.bot.repository.get_tracked_players(guild_id)
        
        if not tracked_players:
            embed = Embed(
                title="📋 追蹤名單",
                description="目前沒有任何玩家在追蹤名單中",
                color=0x95A5A6
            )
            embed.add_field(
                name="💡 提示",
                value="使用 `/join` 指令加入追蹤",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=not public)
            return
        
        # 建立玩家列表
        embed = Embed(
            title="📋 追蹤中的玩家",
            description=f"共 **{len(tracked_players)}** 位玩家正在參與",
            color=0x3498DB
        )
        
        # 批次取得玩家資訊和統計
        player_list = []
        for i, player in enumerate(tracked_players, start=1):
            try:
                user = self.bot.get_user(player.user_id)
                if user is None:
                    user = await self.bot.fetch_user(player.user_id)
                user_name = user.display_name
            except:
                user_name = f"未知使用者"
            
            # 取得統計資料
            stats = await self.bot.repository.get_user_stats(player.user_id, guild_id)
            
            if stats and stats.mention_count > 0:
                ghost_rate = (stats.ghost_count / stats.mention_count * 100)
                status = f"👻 {stats.ghost_count} | 📢 {stats.mention_count} | 🚫 {ghost_rate:.0f}%"
            else:
                status = "🆕 尚無紀錄"
            
            # 計算參與天數
            joined_days = (discord.utils.utcnow() - player.joined_at).days if player.joined_at else 0
            
            player_list.append(f"`{i:2d}.` **{user_name}** - {status}\n     ⏱️ 已參與 {joined_days} 天")
        
        # 分頁顯示（每頁10人）
        page_size = 10
        pages = [player_list[i:i + page_size] for i in range(0, len(player_list), page_size)]
        
        # 只顯示第一頁
        embed.add_field(
            name=f"👥 玩家列表 (第 1/{len(pages)} 頁)",
            value="\n".join(pages[0]),
            inline=False
        )
        
        if len(pages) > 1:
            embed.set_footer(text="提示: 列表過長時僅顯示前 10 位")
        
        await interaction.response.send_message(embed=embed, ephemeral=not public)
    
    @config_group.command(
        name="view",
        description="查看目前的系統設定"
    )
    async def view_config(
        self,
        interaction: discord.Interaction
    ):
        """
        顯示目前的系統參數設定
        """
        config = self.bot.config
        
        embed = Embed(
            title="⚙️ 系統設定",
            description="MentionDodger 目前的參數配置",
            color=0x9B59B6
        )
        
        # 詐欺判定規則
        ghost_rules = config.get("ghost_rules", {})
        embed.add_field(
            name="👻 詐欺判定規則",
            value=(
                f"⏱️ **回應時限**: {ghost_rules.get('response_timeout', 300)} 秒\n"
                f"📝 **最短回應**: {ghost_rules.get('valid_response_min_length', 1)} 字元\n"
                f"🤖 **忽略 Bot**: {'是' if ghost_rules.get('ignore_bot_mentions', True) else '否'}\n"
                f"🎮 **需要加入**: {'是' if ghost_rules.get('need_permission2play', True) else '否'}"
            ),
            inline=False
        )
        
        # 啟用的指令
        enabled_commands = [cmd for cmd, info in config.get("commands", {}).items() if info.get("enable", False)]
        embed.add_field(
            name="💬 啟用的指令",
            value=f"`{'` `'.join(enabled_commands)}`" if enabled_commands else "無",
            inline=False
        )
        
        # 啟用的事件
        enabled_events = [evt for evt, info in config.get("events", {}).items() if info.get("enable", False)]
        embed.add_field(
            name="📡 啟用的事件",
            value=f"`{'` `'.join(enabled_events)}`" if enabled_events else "無",
            inline=False
        )
        
        # 資料庫資訊
        db_config = config.get("database", {})
        embed.add_field(
            name="💾 資料庫",
            value=(
                f"類型: `{db_config.get('type', 'sqlite')}`\n"
                f"路徑: `{db_config.get('path', 'N/A')}`"
            ),
            inline=False
        )
        
        embed.set_footer(text="⚠️ 部分設定需要重啟 Bot 才能生效")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @config_group.command(
        name="set",
        description="修改系統參數（僅管理員）"
    )
    @app_commands.describe(
        parameter="要修改的參數",
        value="新的數值"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_config(
        self,
        interaction: discord.Interaction,
        parameter: Literal["timeout", "min_length"],
        value: int
    ):
        """
        修改系統參數
        需要管理員權限
        """
        config = self.bot.config
        
        # 參數驗證
        if parameter == "timeout":
            if value < 10 or value > 3600:
                await interaction.response.send_message(
                    "❌ 回應時限必須在 10-3600 秒之間",
                    ephemeral=True
                )
                return
            
            old_value = config["ghost_rules"]["response_timeout"]
            config["ghost_rules"]["response_timeout"] = value
            self.bot.scheduler.timeout = value
            param_name = "回應時限"
            unit = "秒"
        
        elif parameter == "min_length":
            if value < 1 or value > 100:
                await interaction.response.send_message(
                    "❌ 最短回應長度必須在 1-100 字元之間",
                    ephemeral=True
                )
                return
            
            old_value = config["ghost_rules"]["valid_response_min_length"]
            config["ghost_rules"]["valid_response_min_length"] = value
            self.bot.evaluator.min_length = value
            param_name = "最短回應"
            unit = "字元"
        
        # 保存到設定檔
        try:
            with open("config/config.yaml", "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, allow_unicode=True)
            
            embed = Embed(
                title="✅ 參數已更新",
                description=f"**{param_name}** 已成功修改",
                color=0x00FF00
            )
            embed.add_field(
                name="舊數值",
                value=f"`{old_value}` {unit}",
                inline=True
            )
            embed.add_field(
                name="新數值",
                value=f"`{value}` {unit}",
                inline=True
            )
            embed.set_footer(text=f"由 {interaction.user.display_name} 修改")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 保存設定失敗: {str(e)}",
                ephemeral=True
            )
    
    @config_group.command(
        name="stats",
        description="查看系統統計資訊"
    )
    async def system_stats(
        self,
        interaction: discord.Interaction
    ):
        """
        顯示系統整體統計
        """
        guild_id = interaction.guild.id
        
        # 取得統計資料
        tracked_players = await self.bot.repository.get_tracked_players(guild_id)
        leaderboard = await self.bot.repository.get_leaderboard(guild_id, limit=100)
        
        # 計算總計
        total_tracked = len(tracked_players)
        total_players_with_stats = len(leaderboard)
        total_ghosts = sum(s.ghost_count for s in leaderboard)
        total_mentions = sum(s.mention_count for s in leaderboard)
        avg_response_rate = sum(s.response_rate for s in leaderboard) / len(leaderboard) if leaderboard else 0
        
        # 取得 pending 任務數量
        pending_count = self.bot.scheduler.get_pending_count()
        
        embed = Embed(
            title="📊 系統統計資訊",
            description=f"**{interaction.guild.name}** 的詐欺追蹤統計",
            color=0xE74C3C
        )
        
        embed.add_field(
            name="👥 玩家統計",
            value=(
                f"追蹤中: **{total_tracked}** 人\n"
                f"有紀錄: **{total_players_with_stats}** 人"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📢 提及統計",
            value=(
                f"總提及: **{total_mentions}** 次\n"
                f"待回應: **{pending_count}** 個"
            ),
            inline=True
        )
        
        embed.add_field(
            name="👻 詐欺統計",
            value=(
                f"總詐欺: **{total_ghosts}** 次\n"
                f"詐欺率: **{(1-avg_response_rate)*100:.1f}%**"
            ),
            inline=True
        )
        
        # 找出最活躍的詐欺犯
        if leaderboard:
            top_ghost = leaderboard[0]
            try:
                user = self.bot.get_user(top_ghost.user_id)
                if user is None:
                    user = await self.bot.fetch_user(top_ghost.user_id)
                top_name = user.display_name
            except:
                top_name = "未知使用者"
            
            embed.add_field(
                name="🏆 詐欺之王",
                value=f"**{top_name}** - {top_ghost.ghost_count} 次詐欺",
                inline=False
            )
        
        # 系統資訊
        embed.add_field(
            name="⚙️ 系統狀態",
            value=(
                f"Bot 延遲: **{round(self.bot.latency * 1000)}ms**\n"
                f"伺服器數: **{len(self.bot.guilds)}** 個\n"
                f"資料庫: `{self.bot.config['database']['type']}`"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"統計時間: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @config_group.command(
        name="export",
        description="匯出伺服器的統計資料（僅管理員）"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def export_data(
        self,
        interaction: discord.Interaction
    ):
        """
        匯出統計資料為 CSV 檔案
        """
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild.id
        leaderboard = await self.bot.repository.get_leaderboard(guild_id, limit=1000)
        
        if not leaderboard:
            await interaction.followup.send("❌ 沒有可匯出的資料", ephemeral=True)
            return
        
        # 建立 CSV 內容
        csv_lines = ["排名,使用者ID,使用者名稱,詐欺次數,提及次數,回應率"]
        
        for i, stats in enumerate(leaderboard, start=1):
            try:
                user = self.bot.get_user(stats.user_id)
                if user is None:
                    user = await self.bot.fetch_user(stats.user_id)
                user_name = user.display_name.replace(",", "，")  # 避免破壞 CSV 格式
            except:
                user_name = "未知使用者"
            
            csv_lines.append(
                f"{i},{stats.user_id},{user_name},{stats.ghost_count},"
                f"{stats.mention_count},{stats.response_rate:.2%}"
            )
        
        csv_content = "\n".join(csv_lines)
        
        # 建立檔案
        import io
        file = discord.File(
            io.BytesIO(csv_content.encode("utf-8-sig")),  # 使用 UTF-8 with BOM 以支援 Excel
            filename=f"ghost_stats_{interaction.guild.name}_{discord.utils.utcnow().strftime('%Y%m%d')}.csv"
        )
        
        embed = Embed(
            title="📥 資料匯出完成",
            description=f"已匯出 **{len(leaderboard)}** 筆資料",
            color=0x00FF00
        )
        
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    
    @config_group.command(
        name="reset",
        description="重置伺服器資料（僅管理員，危險操作）"
    )
    @app_commands.describe(
        confirm="請輸入伺服器名稱以確認重置"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_server(
        self,
        interaction: discord.Interaction,
        confirm: str
    ):
        """
        重置整個伺服器的統計資料
        需要輸入伺服器名稱確認
        """
        if confirm != interaction.guild.name:
            await interaction.response.send_message(
                f"❌ 確認失敗！請輸入正確的伺服器名稱: `{interaction.guild.name}`",
                ephemeral=True
            )
            return
        
        # 執行重置
        await self.bot.repository.reset_guild_stats(interaction.guild.id)
        
        # 清空玩家追蹤名單
        tracked_players = await self.bot.repository.get_tracked_players(interaction.guild.id)
        for player in tracked_players:
            await self.bot.repository.remove_player(player.user_id, interaction.guild.id)
        
        embed = Embed(
            title="🗑️ 伺服器資料已重置",
            description="所有統計資料和追蹤名單已清空",
            color=0xFF0000
        )
        embed.add_field(
            name="⚠️ 已刪除",
            value=(
                "• 所有詐欺紀錄\n"
                "• 所有統計資料\n"
                "• 所有玩家追蹤\n"
                "• 所有待處理任務"
            ),
            inline=False
        )
        embed.set_footer(text=f"由 {interaction.user.display_name} 執行重置")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    @set_config.error
    @reset_server.error
    @export_data.error
    async def config_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """
        錯誤處理
        """
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ 你沒有權限執行此指令（需要管理員權限）",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ 發生錯誤: {str(error)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCommand(bot))