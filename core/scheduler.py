"""
Timeout 排程器
職責: 在 mention 發生後啟動計時器,若超時則標記為詐欺
"""
import asyncio
import logging
from typing import Dict
from datetime import datetime
from database.repository import GhostRepository
from database.models import MentionRecord

logger = logging.getLogger("MentionDodger.Scheduler")


class TimeoutScheduler:
    def __init__(self, repository: GhostRepository, timeout_seconds: int):
        self.repo = repository
        self.timeout = timeout_seconds
        self.pending_tasks: Dict[int, asyncio.Task] = {}
        logger.info(f"TimeoutScheduler 已初始化 (timeout: {timeout_seconds}s)")
    
    def schedule_timeout(self, record: MentionRecord) -> None:
        """
        為一筆 mention 設定 timeout 任務
        
        Args:
            record: MentionRecord 物件 (必須有 id)
        """
        if record.id is None:
            logger.error("無法排程 timeout: record.id 為 None")
            return
        
        # 如果該 record 已有任務在執行，先取消舊的
        if record.id in self.pending_tasks:
            logger.warning(f"Record {record.id} 已有 timeout 任務，將取消舊任務")
            self.cancel_timeout(record.id)
        
        # 建立新任務
        task = asyncio.create_task(
            self._timeout_handler(record),
            name=f"timeout_{record.id}"  # 便於 debug
        )
        
        # 註冊完成後的清理回調
        task.add_done_callback(lambda t: self._cleanup_task(record.id, t))
        
        self.pending_tasks[record.id] = task
        logger.debug(f"已排程 timeout 任務: record_id={record.id}, timeout={self.timeout}s")
    
    async def _timeout_handler(self, record: MentionRecord) -> None:
        """
        等待 timeout 時間後執行詐欺判定
        
        處理流程:
        1. 等待 timeout 秒數
        2. 從資料庫重新讀取最新狀態
        3. 若仍未回應，標記為詐欺
        """
        try:
            logger.debug(f"Timeout 計時開始: record_id={record.id}")
            await asyncio.sleep(self.timeout)
            
            # 從資料庫讀取最新狀態 (避免使用過期的記憶體資料)
            updated_record = await self.repo.get_mention_by_id(record.id)
            
            if updated_record is None:
                logger.warning(f"Record {record.id} 已不存在於資料庫")
                return
            
            # 判定是否已回應
            if not updated_record.responded:
                logger.info(f"使用者 {record.mentioned_user_id} 超時未回應，標記為詐欺")
                
                # 原子性更新 (先標記 ghost，再更新統計)
                await self.repo.mark_as_ghost(record.id)
                await self.repo.increment_ghost_count(
                    user_id=record.mentioned_user_id,
                    guild_id=record.guild_id
                )
                
                logger.debug(f"詐欺紀錄已更新: record_id={record.id}")
            else:
                logger.debug(f"Record {record.id} 已被標記為已回應，跳過詐欺判定")
        
        except asyncio.CancelledError:
            # 任務被取消 (使用者及時回應)
            logger.debug(f"Timeout 任務已取消: record_id={record.id} (使用者已回應)")
            raise  # 重新拋出以正確結束任務
        
        except Exception as e:
            logger.error(f"Timeout 處理發生錯誤: record_id={record.id}, error={e}", exc_info=True)
    
    def cancel_timeout(self, record_id: int) -> bool:
        """
        取消 timeout (當使用者回應時)
        
        Args:
            record_id: 要取消的 record ID
        
        Returns:
            bool: 是否成功取消 (False 表示任務不存在或已完成)
        """
        if record_id not in self.pending_tasks:
            logger.debug(f"嘗試取消不存在的任務: record_id={record_id}")
            return False
        
        task = self.pending_tasks[record_id]
        
        if task.done():
            # 任務已完成 (可能已超時或已被取消)
            logger.debug(f"任務已完成，無需取消: record_id={record_id}")
            return False
        
        # 取消任務
        task.cancel()
        logger.debug(f"已取消 timeout 任務: record_id={record_id}")
        
        # 立即清理 (不等待 done_callback)
        self.pending_tasks.pop(record_id, None)
        return True
    
    def _cleanup_task(self, record_id: int, task: asyncio.Task) -> None:
        """
        任務完成後的清理回調
        
        Args:
            record_id: Record ID
            task: 已完成的 Task
        """
        # 從 pending_tasks 中移除
        self.pending_tasks.pop(record_id, None)
        
        # 處理任務異常 (非 CancelledError)
        if not task.cancelled() and task.exception() is not None:
            logger.error(
                f"任務執行時發生未捕獲的異常: record_id={record_id}, "
                f"exception={task.exception()}"
            )
    
    def get_pending_count(self) -> int:
        """取得目前 pending 的任務數量 (for monitoring)"""
        return len(self.pending_tasks)
    
    def is_pending(self, record_id: int) -> bool:
        """檢查某個 record 是否有 pending 的 timeout"""
        return record_id in self.pending_tasks and not self.pending_tasks[record_id].done()
    
    async def cancel_all(self) -> None:
        """
        取消所有 pending 的任務
        """
        logger.info(f"取消所有 timeout 任務 (共 {len(self.pending_tasks)} 個)")
        
        for record_id, task in list(self.pending_tasks.items()):
            if not task.done():
                task.cancel()
        
        # 等待所有任務完成清理
        if self.pending_tasks:
            await asyncio.gather(*self.pending_tasks.values(), return_exceptions=True)
        
        self.pending_tasks.clear()
        logger.info("所有 timeout 任務已取消")
    
    async def restore_pending_timeouts(self) -> None:
        """
        Bot 重啟後恢復未完成的 timeout
        
        查詢資料庫中所有 responded=False 且 is_ghost=False 的紀錄
        計算剩餘時間並重新排程
        """
        logger.info("嘗試恢復 pending timeouts...")
        
        pending_mentions = await self.repo.get_all_pending_mentions()
        
        for mention in pending_mentions:
            # 計算從 mention_time 到現在經過的時間
            elapsed = (datetime.now() - mention.mention_time).total_seconds()
            remaining = max(0, self.timeout - elapsed)
            
            if remaining > 0:
                # 還沒超時，重新排程
                # 需要修改 schedule_timeout 支援自訂 timeout
                self.schedule_timeout(mention)
            else:
                # 已超時，直接標記為詐欺
                await self.repo.mark_as_ghost(mention.id)
                await self.repo.increment_ghost_count(
                    mention.mentioned_user_id,
                    mention.guild_id
                )
        
        logger.info("Timeout 恢復完成")