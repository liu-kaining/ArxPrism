"""
ArxPrism Task Manager

基于 Redis 的任务状态管理器。
支持任务的创建、查询、暂停、恢复、取消等操作。

Redis 存储结构:
- arxprism:task:{task_id} → Task JSON (TTL 7天)
- arxprism:task:{task_id}:pause → 暂停信号 (存在即暂停)
- arxprism:task:{task_id}:cancel → 取消信号 (存在即取消)
- arxprism:tasks:recent → 最近100个任务ID列表

Reference: ARCHITECTURE.md Section 5 (扩展)
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import uuid4

import redis.asyncio as aioredis

from src.core.config import settings
from src.models.task_models import (
    Task,
    TaskStatus,
    TaskProgress,
    PaperProcessingResult,
    PaperProcessingStatus,
    DomainPreset,
    DOMAIN_PRESETS,
    get_domain_preset,
)

logger = logging.getLogger(__name__)

# Redis Key 前缀
TASK_KEY_PREFIX = "arxprism:task:"
PAUSE_KEY_PREFIX = "arxprism:task:{}:pause"
CANCEL_KEY_PREFIX = "arxprism:task:{}:cancel"
RECENT_TASKS_KEY = "arxprism:tasks:recent"

# 任务过期时间 (7天)
TASK_TTL = 7 * 24 * 60 * 60

# 最近任务列表最大长度
MAX_RECENT_TASKS = 100


class TaskManager:
    """
    Redis 任务管理器 (异步实现).

    提供:
    - 任务创建、查询、更新
    - 任务暂停/恢复/取消信号
    - 任务进度更新
    - 最近任务列表维护
    """

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """初始化 Redis 连接."""
        if self._redis is None:
            logger.info(f"Connecting to Redis at {settings.redis_url}")
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis connection established")

    async def close(self) -> None:
        """关闭 Redis 连接."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")

    def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 客户端."""
        if self._redis is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._redis

    # =========================================================================
    # 任务 CRUD 操作
    # =========================================================================

    async def create_task(
        self,
        query: str,
        domain_preset: str = "sre",
        max_results: int = 10
    ) -> Task:
        """
        创建新任务.

        Args:
            query: arXiv 搜索查询
            domain_preset: 领域预设
            max_results: 最大论文数

        Returns:
            创建的 Task 对象
        """
        task_id = str(uuid4())
        now = datetime.utcnow()

        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            query=query,
            domain_preset=domain_preset,
            max_results=max_results,
            progress=TaskProgress(total=0, processed=0),
            results=[],
            created_at=now,
            updated_at=now
        )

        # 存储任务
        await self._save_task(task)

        # 添加到最近任务列表
        await self._add_to_recent_tasks(task_id)

        logger.info(f"Created task {task_id}: query='{query}', domain='{domain_preset}'")
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务详情.

        Args:
            task_id: 任务 ID

        Returns:
            Task 对象，不存在返回 None
        """
        redis = self._get_redis()
        key = f"{TASK_KEY_PREFIX}{task_id}"

        data = await redis.get(key)
        if data is None:
            return None

        return Task.model_validate_json(data)

    async def update_task(self, task: Task) -> None:
        """
        更新任务状态.

        Args:
            task: Task 对象
        """
        task.updated_at = datetime.utcnow()
        await self._save_task(task)

    async def _save_task(self, task: Task) -> None:
        """保存任务到 Redis."""
        redis = self._get_redis()
        key = f"{TASK_KEY_PREFIX}{task.task_id}"

        await redis.setex(
            key,
            TASK_TTL,
            task.model_dump_json()
        )

    async def _add_to_recent_tasks(self, task_id: str) -> None:
        """添加任务 ID 到最近任务列表."""
        redis = self._get_redis()

        # 使用 LPUSH 添加到列表头部
        await redis.lpush(RECENT_TASKS_KEY, task_id)

        # 保留最近 100 个
        await redis.ltrim(RECENT_TASKS_KEY, 0, MAX_RECENT_TASKS - 1)

    _ACTIVE_STATUSES = frozenset(
        {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED}
    )
    _TERMINAL_STATUSES = frozenset(
        {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    )

    def _task_matches_list_filter(
        self,
        task: Task,
        status: Optional[TaskStatus],
        active_only: bool,
        terminal_only: bool,
    ) -> bool:
        if status is not None:
            return task.status == status
        if active_only:
            return task.status in self._ACTIVE_STATUSES
        if terminal_only:
            return task.status in self._TERMINAL_STATUSES
        return True

    async def list_recent_tasks_page(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        status: Optional[TaskStatus] = None,
        active_only: bool = False,
        terminal_only: bool = False,
    ) -> Tuple[List[Task], int]:
        """
        在最近任务 ID 列表（最多 MAX_RECENT_TASKS 条）上筛选后分页。

        顺序与 Redis 列表一致（新任务在前）。
        """
        redis = self._get_redis()
        task_ids = await redis.lrange(
            RECENT_TASKS_KEY, 0, MAX_RECENT_TASKS - 1
        )
        if not task_ids:
            return [], 0

        pipe = redis.pipeline()
        for tid in task_ids:
            pipe.get(f"{TASK_KEY_PREFIX}{tid}")
        raw_rows = await pipe.execute()

        loaded: List[Task] = []
        for raw in raw_rows:
            if not raw:
                continue
            try:
                loaded.append(Task.model_validate_json(raw))
            except Exception as e:
                logger.warning("Skip invalid task JSON in recent list: %s", e)

        filtered = [
            t
            for t in loaded
            if self._task_matches_list_filter(
                t, status, active_only, terminal_only
            )
        ]
        total = len(filtered)
        page = filtered[offset : offset + limit]
        return page, total

    async def list_recent_tasks(self, limit: int = 20) -> List[Task]:
        """
        获取最近的任务列表（不筛选，取 Redis 序前 limit 条已加载任务）。

        兼容旧调用；新接口请用 list_recent_tasks_page。
        """
        tasks, _ = await self.list_recent_tasks_page(
            offset=0,
            limit=limit,
            status=None,
            active_only=False,
            terminal_only=False,
        )
        return tasks

    # =========================================================================
    # 任务进度更新
    # =========================================================================

    async def update_progress(
        self,
        task_id: str,
        total: Optional[int] = None,
        processed: Optional[int] = None,
        succeeded: Optional[int] = None,
        skipped: Optional[int] = None,
        failed: Optional[int] = None,
        current_paper_id: Optional[str] = None,
        current_paper_title: Optional[str] = None
    ) -> None:
        """
        更新任务进度.

        Args:
            task_id: 任务 ID
            total: 总论文数
            processed: 已处理数
            succeeded: 成功数
            skipped: 跳过数
            failed: 失败数
            current_paper_id: 当前处理的论文 ID
            current_paper_title: 当前处理的论文标题
        """
        task = await self.get_task(task_id)
        if task is None:
            logger.warning(f"Task {task_id} not found for progress update")
            return

        # 更新进度
        if total is not None:
            task.progress.total = total
        if processed is not None:
            task.progress.processed = processed
        if succeeded is not None:
            task.progress.succeeded = succeeded
        if skipped is not None:
            task.progress.skipped = skipped
        if failed is not None:
            task.progress.failed = failed
        if current_paper_id is not None:
            task.progress.current_paper_id = current_paper_id
        if current_paper_title is not None:
            task.progress.current_paper_title = current_paper_title

        await self.update_task(task)

    async def add_paper_result(
        self,
        task_id: str,
        result: PaperProcessingResult
    ) -> None:
        """
        添加论文处理结果.

        Args:
            task_id: 任务 ID
            result: 论文处理结果
        """
        task = await self.get_task(task_id)
        if task is None:
            logger.warning(f"Task {task_id} not found for adding result")
            return

        # 添加结果
        result.processed_at = datetime.utcnow()
        task.results.append(result)

        # 更新进度计数
        task.progress.processed += 1
        if result.status == PaperProcessingStatus.SUCCESS:
            task.progress.succeeded += 1
        elif result.status == PaperProcessingStatus.SKIPPED:
            task.progress.skipped += 1
        elif result.status == PaperProcessingStatus.FAILED:
            task.progress.failed += 1

        # 清空当前处理论文
        task.progress.current_paper_id = None
        task.progress.current_paper_title = None

        await self.update_task(task)

    # =========================================================================
    # 任务状态转换
    # =========================================================================

    async def start_task(self, task_id: str) -> bool:
        """
        将任务标记为运行中.

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task = await self.get_task(task_id)
        if task is None:
            return False

        if task.status != TaskStatus.PENDING:
            logger.warning(f"Task {task_id} cannot be started: status={task.status}")
            return False

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        await self.update_task(task)

        logger.info(f"Task {task_id} started")
        return True

    async def complete_task(
        self, task_id: str, completion_summary: Optional[str] = None
    ) -> bool:
        """
        将任务标记为完成.

        Args:
            task_id: 任务 ID
            completion_summary: 可选说明（如未检索到论文、全部被跳过等）

        Returns:
            是否成功
        """
        task = await self.get_task(task_id)
        if task is None:
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        if completion_summary is not None:
            task.completion_summary = completion_summary
        await self.update_task(task)

        # 清除暂停和取消信号
        await self.clear_pause_signal(task_id)
        await self.clear_cancel_signal(task_id)

        logger.info(
            "Task %s completed%s",
            task_id,
            f" — {completion_summary}" if completion_summary else "",
        )
        return True

    async def fail_task(self, task_id: str, error_message: str) -> bool:
        """
        将任务标记为失败.

        Args:
            task_id: 任务 ID
            error_message: 错误信息

        Returns:
            是否成功
        """
        task = await self.get_task(task_id)
        if task is None:
            return False

        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.completed_at = datetime.utcnow()
        await self.update_task(task)

        # 清除暂停信号
        await self.clear_pause_signal(task_id)

        logger.error(f"Task {task_id} failed: {error_message}")
        return True

    # =========================================================================
    # 暂停/恢复/取消 操作
    # =========================================================================

    async def pause_task(self, task_id: str) -> bool:
        """
        暂停任务.

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task = await self.get_task(task_id)
        if task is None:
            return False

        if not task.can_pause:
            logger.warning(f"Task {task_id} cannot be paused: status={task.status}")
            return False

        # 设置暂停信号
        redis = self._get_redis()
        pause_key = PAUSE_KEY_PREFIX.format(task_id)
        await redis.setex(pause_key, TASK_TTL, "1")

        task.status = TaskStatus.PAUSED
        await self.update_task(task)

        logger.info(f"Task {task_id} paused")
        return True

    async def resume_task(self, task_id: str) -> bool:
        """
        恢复任务.

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task = await self.get_task(task_id)
        if task is None:
            return False

        if not task.can_resume:
            logger.warning(f"Task {task_id} cannot be resumed: status={task.status}")
            return False

        # 清除暂停信号
        await self.clear_pause_signal(task_id)

        task.status = TaskStatus.RUNNING
        await self.update_task(task)

        logger.info(f"Task {task_id} resumed")
        return True

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务.

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task = await self.get_task(task_id)
        if task is None:
            return False

        if not task.can_cancel:
            logger.warning(f"Task {task_id} cannot be cancelled: status={task.status}")
            return False

        # 设置取消信号
        redis = self._get_redis()
        cancel_key = CANCEL_KEY_PREFIX.format(task_id)
        await redis.setex(cancel_key, TASK_TTL, "1")

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        await self.update_task(task)

        # 清除暂停信号
        await self.clear_pause_signal(task_id)

        logger.info(f"Task {task_id} cancelled")
        return True

    async def is_paused(self, task_id: str) -> bool:
        """检查任务是否被暂停."""
        redis = self._get_redis()
        pause_key = PAUSE_KEY_PREFIX.format(task_id)
        return await redis.exists(pause_key) > 0

    async def is_cancelled(self, task_id: str) -> bool:
        """检查任务是否被取消."""
        redis = self._get_redis()
        cancel_key = CANCEL_KEY_PREFIX.format(task_id)
        return await redis.exists(cancel_key) > 0

    async def clear_pause_signal(self, task_id: str) -> None:
        """清除暂停信号."""
        redis = self._get_redis()
        pause_key = PAUSE_KEY_PREFIX.format(task_id)
        await redis.delete(pause_key)

    async def clear_cancel_signal(self, task_id: str) -> None:
        """清除取消信号."""
        redis = self._get_redis()
        cancel_key = CANCEL_KEY_PREFIX.format(task_id)
        await redis.delete(cancel_key)

    # =========================================================================
    # 辅助方法
    # =========================================================================

    async def wait_while_paused(self, task_id: str, check_interval: float = 2.0) -> bool:
        """
        当任务被暂停时阻塞等待，直到恢复或取消.

        Args:
            task_id: 任务 ID
            check_interval: 检查间隔 (秒)

        Returns:
            True 如果恢复，False 如果被取消
        """
        import asyncio

        while await self.is_paused(task_id):
            # 检查是否被取消
            if await self.is_cancelled(task_id):
                return False
            await asyncio.sleep(check_interval)

        return not await self.is_cancelled(task_id)

    async def wipe_all_arxprism_keys(self) -> int:
        """
        删除 Redis 中所有 `arxprism:*` 键（任务 JSON、暂停/取消信号、最近任务列表等）。

        不执行 FLUSHDB，避免影响同库中的 Celery broker 等其他数据。
        """
        redis = self._get_redis()
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = await redis.scan(
                cursor=cursor, match="arxprism:*", count=500
            )
            if keys:
                deleted += int(await redis.delete(*keys))
            if cursor == 0:
                break
        logger.warning("Redis arxprism:* keys wiped: %s keys deleted", deleted)
        return deleted


# 单例实例
task_manager = TaskManager()


async def get_task_manager() -> TaskManager:
    """获取任务管理器实例 (依赖注入)."""
    if task_manager._redis is None:
        await task_manager.connect()
    return task_manager
