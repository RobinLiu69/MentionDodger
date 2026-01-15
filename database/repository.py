"""
資料庫操作封裝 (Repository Pattern)
"""
import aiosqlite
from typing import List, Optional
from database.models import MentionRecord, GhostStats
from datetime import datetime
import hashlib # 之後新增 敏感資料進行 SHA-256

class GhostRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_db(self):
        """
        初始化資料庫表格
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    mentioned_user_id INTEGER NOT NULL,
                    mentioner_user_id INTEGER NOT NULL,
                    mention_time TIMESTAMP NOT NULL,
                    responded BOOLEAN DEFAULT FALSE,
                    response_time TIMESTAMP,
                    is_ghost BOOLEAN DEFAULT FALSE
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ghost_stats (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    ghost_count INTEGER DEFAULT 0,
                    mention_count INTEGER DEFAULT 0,
                    response_rate REAL DEFAULT 0.0,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # 建立索引以提升查詢效能
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_mentions_pending 
                ON mentions(mentioned_user_id, channel_id, responded)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ghost_stats_guild 
                ON ghost_stats(guild_id, ghost_count DESC)
            """)
            
            await db.commit()
    
    # ==================== Mention 相關操作 ====================
    
    async def add_mention(self, record: MentionRecord) -> int:
        """
        新增一筆 mention 紀錄
        返回: 新建立的 record_id
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 1. 插入 mention 紀錄
            cursor = await db.execute("""
                INSERT INTO mentions (
                    guild_id, channel_id, message_id,
                    mentioned_user_id, mentioner_user_id, mention_time
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.guild_id,
                record.channel_id,
                record.message_id,
                record.mentioned_user_id,
                record.mentioner_user_id,
                record.mention_time.isoformat()
            ))
            
            record_id = cursor.lastrowid
            
            # 2. 更新統計
            await db.execute("""
                INSERT INTO ghost_stats (user_id, guild_id, mention_count, last_updated)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    mention_count = mention_count + 1,
                    last_updated = ?
            """, (
                record.mentioned_user_id, 
                record.guild_id, 
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            await db.commit()
            
            return record_id
    
    async def get_mention_by_id(self, record_id: int) -> Optional[MentionRecord]:
        """
        根據 ID 取得單筆 mention 紀錄
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM mentions WHERE id = ?", 
                (record_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_mention_record(row)
    
    async def get_pending_mentions(
        self, 
        user_id: int, 
        channel_id: int
    ) -> List[MentionRecord]:
        """
        取得某使用者在某頻道中尚未回應的 mention
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM mentions
                WHERE mentioned_user_id = ?
                  AND channel_id = ?
                  AND responded = FALSE
                  AND is_ghost = FALSE
                ORDER BY mention_time DESC
            """, (user_id, channel_id))
            
            rows = await cursor.fetchall()
            return [self._row_to_mention_record(row) for row in rows]
    
    async def mark_as_responded(self, record_id: int, response_time: datetime):
        """
        標記為已回應
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # 1. 先取得 mention 資訊 (需要 user_id 和 guild_id)
            cursor = await db.execute(
                "SELECT mentioned_user_id, guild_id FROM mentions WHERE id = ?",
                (record_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return  # 找不到紀錄
            
            user_id = row["mentioned_user_id"]
            guild_id = row["guild_id"]
            
            # 2. 更新 mention 狀態
            await db.execute("""
                UPDATE mentions
                SET responded = TRUE,
                    response_time = ?
                WHERE id = ?
            """, (response_time.isoformat(), record_id))
            
            # 3. 重新計算回應率
            # 計算已回應的次數
            cursor = await db.execute("""
                SELECT COUNT(*) FROM mentions
                WHERE mentioned_user_id = ?
                  AND guild_id = ?
                  AND responded = TRUE
            """, (user_id, guild_id))
            responded_count = (await cursor.fetchone())[0]
            
            # 取得總 mention 數
            cursor = await db.execute("""
                SELECT mention_count FROM ghost_stats
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            stats_row = await cursor.fetchone()
            
            if stats_row and stats_row[0] > 0:
                mention_count = stats_row[0]
                response_rate = responded_count / mention_count
                
                await db.execute("""
                    UPDATE ghost_stats
                    SET response_rate = ?,
                        last_updated = ?
                    WHERE user_id = ? AND guild_id = ?
                """, (
                    response_rate, 
                    datetime.now().isoformat(), 
                    user_id, 
                    guild_id
                ))
            
            await db.commit()
    
    async def mark_as_ghost(self, record_id: int):
        """
        標記為詐欺 (timeout 時觸發)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 只更新尚未被標記的紀錄
            await db.execute("""
                UPDATE mentions
                SET is_ghost = TRUE
                WHERE id = ?
                  AND is_ghost = FALSE
            """, (record_id,))
            await db.commit()
    
    # ==================== 統計資料操作 ====================
    
    async def increment_ghost_count(self, user_id: int, guild_id: int):
        """
        增加詐欺計數 (當 timeout 觸發時)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 1. 增加 ghost_count
            await db.execute("""
                INSERT INTO ghost_stats (user_id, guild_id, ghost_count, last_updated)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    ghost_count = ghost_count + 1,
                    last_updated = ?
            """, (
                user_id, 
                guild_id, 
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            # 2. 重新計算回應率
            cursor = await db.execute("""
                SELECT COUNT(*) FROM mentions
                WHERE mentioned_user_id = ?
                  AND guild_id = ?
                  AND responded = TRUE
            """, (user_id, guild_id))
            responded_count = (await cursor.fetchone())[0]
            
            cursor = await db.execute("""
                SELECT mention_count FROM ghost_stats
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            row = await cursor.fetchone()
            
            if row and row[0] > 0:
                mention_count = row[0]
                response_rate = responded_count / mention_count
                
                await db.execute("""
                    UPDATE ghost_stats
                    SET response_rate = ?
                    WHERE user_id = ? AND guild_id = ?
                """, (response_rate, user_id, guild_id))
            
            await db.commit()
    
    async def get_user_stats(self, user_id: int, guild_id: int) -> Optional[GhostStats]:
        """
        取得特定使用者的統計資料
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM ghost_stats
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            
            row = await cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_ghost_stats(row)
    
    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[GhostStats]:
        """
        取得排行榜 (依詐欺次數降序)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM ghost_stats
                WHERE guild_id = ?
                  AND mention_count > 0
                ORDER BY ghost_count DESC, response_rate ASC
                LIMIT ?
            """, (guild_id, limit))
            
            rows = await cursor.fetchall()
            return [self._row_to_ghost_stats(row) for row in rows]
    
    async def reset_user_stats(self, user_id: int, guild_id: int):
        """
        重置特定使用者的統計
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM ghost_stats
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            
            await db.execute("""
                DELETE FROM mentions
                WHERE mentioned_user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            
            await db.commit()
    
    async def reset_guild_stats(self, guild_id: int):
        """
        重置整個伺服器的統計
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ghost_stats WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM mentions WHERE guild_id = ?", (guild_id,))
            await db.commit()
    
    async def get_all_pending_mentions(self) -> List[MentionRecord]:
        """
        取得所有尚未回應且未被標記為詐欺的 mention
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM mentions
                WHERE responded = FALSE
                  AND is_ghost = FALSE
                ORDER BY mention_time ASC
            """)
            rows = await cursor.fetchall()
            return [self._row_to_mention_record(row) for row in rows]
    
    # ==================== 內部輔助方法 ====================
    
    @staticmethod
    def _row_to_mention_record(row) -> MentionRecord:
        """
        將資料庫 Row 轉換為 MentionRecord
        """
        return MentionRecord(
            id=row["id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            message_id=row["message_id"],
            mentioned_user_id=row["mentioned_user_id"],
            mentioner_user_id=row["mentioner_user_id"],
            mention_time=datetime.fromisoformat(row["mention_time"]),
            responded=bool(row["responded"]),
            response_time=datetime.fromisoformat(row["response_time"]) if row["response_time"] else None,
            is_ghost=bool(row["is_ghost"])
        )
    
    @staticmethod
    def _row_to_ghost_stats(row) -> GhostStats:
        """
        將資料庫 Row 轉換為 GhostStats
        """
        return GhostStats(
            user_id=row["user_id"],
            guild_id=row["guild_id"],
            ghost_count=row["ghost_count"],
            mention_count=row["mention_count"],
            response_rate=row["response_rate"],
            last_updated=datetime.fromisoformat(row["last_updated"]) if row["last_updated"] else None
        )
    
        