"""
Celery Worker Tasks

配置 Celery 实例 (broker 连 Redis)。
定义异步转同步的 Celery Task。
流水线: arxiv_radar -> llm_extractor -> neo4j_client.upsert_paper_graph

优雅降级: 如果 Redis 不可用，回退为同步函数调用 (方便本地 Debug)。

Reference: ARCHITECTURE.md Section 2, CODE_REVIEW.md Section 2
"""

import asyncio
import logging
import threading
from typing import Optional

from celery import Celery

from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.models.schemas import PaperExtractionResponse
from src.services.arxiv_radar import arxiv_radar, PaperContent
from src.services.llm_extractor import llm_extractor

logger = logging.getLogger(__name__)


# =============================================================================
# 全局事件循环管理 (解决 Celery 中嵌套事件循环的问题)
# =============================================================================

_event_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    获取或创建事件循环。

    Celery Task 运行在单独的进程中，可以使用全局事件循环。
    避免每个 paper 都创建新事件循环。
    """
    global _event_loop
    if _event_loop is None:
        with _loop_lock:
            if _event_loop is None:
                _event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_event_loop)
    return _event_loop


def _run_async(coro):
    """
    在事件循环中运行协程。

    使用全局单一事件循环，避免重复创建销毁的开销。
    """
    loop = _get_or_create_event_loop()
    return loop.run_until_complete(coro)


# =============================================================================
# Redis 可用性检测 & 优雅降级
# =============================================================================

def _is_redis_available() -> bool:
    """检查 Redis 是否可用."""
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}. Falling back to sync mode.")
        return False


# =============================================================================
# Celery 应用 (延迟初始化)
# =============================================================================
_celery_app: Optional[Celery] = None


def get_celery_app() -> Optional[Celery]:
    """获取 Celery 应用实例，Redis 不可用时返回 None."""
    global _celery_app
    if _celery_app is not None:
        return _celery_app

    if not _is_redis_available():
        return None

    _celery_app = Celery(
        "arxprism",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["src.worker.tasks"]
    )

    _celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=300,  # 5 minutes per task
        task_time_limit=600,  # 10 minutes hard limit
        # Celery 5.x: 必须显式开启，否则 Redis 没 ready 时直接退出
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
    )

    return _celery_app


# =============================================================================
# 核心处理逻辑 (Celery Task 和同步模式共用)
# =============================================================================

async def _process_paper_async(paper_content: dict) -> dict:
    """
    论文处理核心逻辑 (异步版本，供 Celery 和同步模式共用)。

    流水线:
    1. 重建 PaperContent 对象
    2. 调用 LLM 萃取
    3. 检查领域相关性
    4. 写入 Neo4j

    Args:
        paper_content: Dict representation of PaperContent

    Returns:
        Dict with status and paper_id
    """
    paper_id = paper_content.get("arxiv_id", "unknown")
    logger.info(f"Processing paper: {paper_id}")

    try:
        # Step 1: 重建 PaperContent
        content = PaperContent(
            arxiv_id=paper_content["arxiv_id"],
            title=paper_content["title"],
            authors=paper_content["authors"],
            published_date=paper_content["published_date"],
            text_content=paper_content["text_content"],
            html_url=paper_content["html_url"]
        )

        # Step 2: 调用 LLM 萃取 (异步)
        logger.info(f"Paper {paper_id}: Running LLM extraction...")
        extraction = await llm_extractor.extract(
            paper_text=content.text_content,
            paper_id=content.arxiv_id,
            title=content.title,
            authors=content.authors,
            publication_date=content.published_date
        )

        if extraction is None:
            logger.warning(f"Paper {paper_id}: Extraction returned None")
            # 提取失败时抛出异常，触发 Celery 重试
            raise RuntimeError(f"Extraction failed for paper {paper_id}")

        # Step 3: 检查领域相关性
        if not extraction.is_relevant_to_domain:
            logger.info(
                f"Paper {paper_id}: Domain gatekeeper rejected - "
                f"not in SRE/cloud-native/AIOps domain"
            )
            return {"status": "skipped", "paper_id": paper_id, "reason": "domain_not_relevant"}

        # Step 4: 写入 Neo4j (异步)
        logger.info(f"Paper {paper_id}: Upserting to Neo4j graph...")
        upsert_success = await neo4j_client.upsert_paper_graph(extraction)

        if not upsert_success:
            logger.error(f"Paper {paper_id}: Neo4j upsert failed")
            raise RuntimeError(f"Neo4j upsert failed for paper {paper_id}")

        logger.info(f"Paper {paper_id}: Successfully processed")
        return {"status": "success", "paper_id": paper_id}

    except Exception as e:
        logger.error(f"Paper {paper_id}: Processing failed - {e}")
        raise


# =============================================================================
# Celery Task 注册
# =============================================================================

def _create_celery_tasks() -> None:
    """创建并注册 Celery Tasks (延迟初始化)."""
    celery_app = get_celery_app()
    if celery_app is None:
        return

    @celery_app.task(
        bind=True,
        max_retries=3,
        default_retry_delay=60,
        name="process_paper_task"
    )
    def process_paper_task(self, paper_content: dict) -> dict:
        """
        Celery Task: 处理单篇论文.

        Args:
            paper_content: Dict representation of PaperContent

        Returns:
            Dict with status and paper_id
        """
        try:
            # 直接运行异步逻辑，不再创建新的事件循环
            return _run_async(_process_paper_async(paper_content))
        except Exception as e:
            logger.error(f"Task failed: {e}")
            # 触发 Celery 重试
            raise self.retry(exc=e)

    # 注册到全局注册表
    global _celery_tasks
    _celery_tasks["process_paper_task"] = process_paper_task
    logger.info("Celery task 'process_paper_task' registered")


# 全局 Task 注册表
_celery_tasks: dict = {}


def get_process_paper_task():
    """获取 process_paper_task 函数 (Celery Task 或同步回退)."""
    if "process_paper_task" in _celery_tasks:
        return _celery_tasks["process_paper_task"]

    celery_app = get_celery_app()
    if celery_app is not None:
        _create_celery_tasks()
        if "process_paper_task" in _celery_tasks:
            return _celery_tasks["process_paper_task"]

    # 返回异步回退函数 (同步模式直接调用 _process_paper_async)
    return _process_paper_async


# =============================================================================
# 同步回退模式 (Redis 不可用时使用)
# =============================================================================

def trigger_pipeline_sync(topic_query: str, max_results: int = 10) -> dict:
    """
    同步回退: 流水线触发 (Redis 不可用时)。

    允许在没有 Redis/Celery 基础设施的情况下进行本地调试。

    Args:
        topic_query: arXiv 搜索查询
        max_results: 最大论文数量

    Returns:
        Dict with processing results
    """
    logger.info(f"[SYNC MODE] Processing pipeline: query='{topic_query}', max_results={max_results}")

    async def _run():
        # Fetch papers
        papers = await arxiv_radar.fetch_recent_papers(topic_query, max_results)
        logger.info(f"[SYNC MODE] Fetched {len(papers)} papers")

        # Process papers
        results = []
        for paper in papers:
            content_dict = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors,
                "published_date": paper.published_date,
                "text_content": paper.text_content,
                "html_url": paper.html_url
            }
            result = await _process_paper_async(content_dict)
            results.append(result)
            logger.debug(f"[SYNC MODE] Processed paper {paper.arxiv_id}: {result['status']}")

        return results

    # Run async code in event loop
    results = _run_async(_run())

    success_count = sum(1 for r in results if r["status"] == "success")
    logger.info(f"[SYNC MODE] Pipeline complete: {success_count}/{len(results)} succeeded")

    return {
        "status": "sync_completed",
        "mode": "synchronous_fallback",
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results
    }


# =============================================================================
# 流水线触发入口
# =============================================================================

def trigger_pipeline_task(topic_query: str, max_results: int = 10) -> dict:
    """
    触发流水线.

    这是 API 调用的主入口。
    如果 Redis 不可用，自动回退到同步模式。

    Args:
        topic_query: arXiv 搜索查询
        max_results: 最大论文数量

    Returns:
        Dict with task IDs and status
    """
    celery_app = get_celery_app()

    if celery_app is None:
        # Redis 不可用 - 回退到同步模式
        return trigger_pipeline_sync(topic_query, max_results)

    # 使用 Celery 异步分发任务
    logger.info(f"Triggering pipeline via Celery: query='{topic_query}', max_results={max_results}")

    async def _run():
        # Fetch papers
        papers = await arxiv_radar.fetch_recent_papers(topic_query, max_results)
        logger.info(f"Fetched {len(papers)} new papers")

        # Ensure task is registered
        task_func = get_process_paper_task()

        # Dispatch tasks
        task_ids = []
        for paper in papers:
            content_dict = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors,
                "published_date": paper.published_date,
                "text_content": paper.text_content,
                "html_url": paper.html_url
            }

            if hasattr(task_func, 'delay'):
                # It's a Celery task
                task = task_func.delay(content_dict)
                task_ids.append(task.id)
                logger.debug(f"Dispatched task {task.id} for paper {paper.arxiv_id}")
            else:
                # It's the async fallback function
                result = await task_func(content_dict)
                logger.debug(f"Async processing for paper {paper.arxiv_id}: {result['status']}")

        return task_ids

    # Run async code in event loop
    task_ids = _run_async(_run())

    logger.info(f"Pipeline triggered: {len(task_ids)} tasks dispatched")
    return {
        "status": "dispatched",
        "task_count": len(task_ids),
        "task_ids": task_ids
    }
