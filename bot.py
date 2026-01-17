import discord
import os
import yaml
from dotenv import load_dotenv
import logging
from discord.ext import commands


from database.repository import GhostRepository
from core.tracker import MentionTracker
from core.evaluator import ResponseEvaluator
from core.scheduler import TimeoutScheduler

# 設定基礎 Log (之後移至 utils/logger.py 統一管理)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MentionDodger")

class GhostBot(commands.Bot):
    def __init__(self) -> None:
        # 1. 載入設定檔
        self.config = self.load_config()
        
        # 2. 設定 Intents
        intents = discord.Intents.default()
        intents.message_content = True  
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            description="MentionDodger - A bot tracking ghosting behavior."
        )

    def load_config(self) -> dict:
        """
        讀取 config/config.yaml
        """
        try:
            with open("config/config.yaml", "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error("找不到 config/config.yaml，請檢查檔案位置。")
            exit(1)

    async def setup_hook(self) -> None:
        """
        Bot 啟動前的異步初始化鉤子
        在這裡載入 Cogs 和連接資料庫
        """
        logger.info(f"--- 初始化 GhostBot ---")
        
        # 1. 初始化資料庫
        self.repository = GhostRepository(self.config["database"]["path"])
        await self.repository.init_db()
        
        # 2. 初始化核心元件
        timeout = self.config["ghost_rules"]["response_timeout"]
        self.tracker = MentionTracker(self.repository, timeout)
        self.evaluator = ResponseEvaluator(
            min_length=self.config["ghost_rules"]["valid_response_min_length"]
        )
        self.scheduler = TimeoutScheduler(self.repository, timeout)
        cog_folders = ["commands", "events"]

        enable_cogs = [key for key, i in (bot.config["commands"] | bot.config["events"]).items() if i["enable"]]

        for folder in cog_folders:
            if not os.path.exists(folder):
                logger.warning(f"目錄 {folder} 不存在，跳過載入。")
                continue
                
            for filename in os.listdir(folder):
                if filename[:-3] not in enable_cogs: continue
                if filename.endswith(".py") and not filename.startswith("__"):
                    extension_name = f"{folder}.{filename[:-3]}"
                    try:
                        await self.load_extension(extension_name)
                        logger.info(f"已載入模組: {extension_name}")
                    except Exception as e:
                        logger.error(f"無法載入模組 {extension_name}: {e}")
        

        await self.tree.sync(guild=discord.Object(id=(os.getenv("GUILD_ID"))))
        
        await self.tree.sync(guild=None)
        logger.info("Slash Commands 已同步")

        logger.info(f"--- 初始化完成，等待連線 ---")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("------")


if __name__ == "__main__":

    bot = GhostBot()

    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        logger.error("Config 中未找到 Token，請檢查設定檔。")
    else:
        try:
            bot.run(token)
        except discord.errors.LoginFailure:
            logger.error("Token 無效，無法登入。")