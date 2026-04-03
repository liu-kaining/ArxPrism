"""
Celery Worker Tasks

配置 Celery 实例 (broker 连 Redis)。
定义异步转同步的 Celery Task。
流水线: arxiv_radar -> llm_extractor -> neo4j_client.upsert_paper_graph

支持:
- 任务状态追踪 (通过 Redis TaskManager)
- 暂停/恢复/取消操作
- 领域预设优化查询

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
from src.models.task_models import (
    TaskStatus,
    PaperProcessingResult,
    PaperProcessingStatus,
)
from src.services.arxiv_radar import arxiv_radar, PaperContent
from src.services.llm_extractor import llm_extractor
from src.services.task_manager import task_manager

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
# Celery 应用
# =============================================================================
#
# 重要：docker-compose 里 worker 的启动命令是：
#   celery -A src.worker.tasks worker ...
# Celery 会在导入该模块时查找名为 `celery` 的 Celery 实例。
# 如果不提供，将报错：
#   Module 'src.worker.tasks' has no attribute 'celery'
#
celery = Celery(
    "arxprism",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.worker.tasks"],
)

celery.conf.update(
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
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

_celery_app: Optional[Celery] = None


def get_celery_app() -> Optional[Celery]:
    """获取 Celery 应用实例，Redis 不可用时返回 None."""
    global _celery_app
    if _celery_app is not None:
        return _celery_app

    if not _is_redis_available():
        return None

    _celery_app = celery
    return celery


# =============================================================================
# 核心处理逻辑 (Celery Task 和同步模式共用)
# =============================================================================

async def _process_paper_async(
    paper_content: dict,
    task_id: Optional[str] = None
) -> PaperProcessingResult:
    """
    论文处理核心逻辑 (异步版本，供 Celery 和同步模式共用)。

    流水线:
    1. 重建 PaperContent 对象
    2. 调用 LLM 萃取
    3. 检查领域相关性
    4. 写入 Neo4j

    Args:
        paper_content: Dict representation of PaperContent
        task_id: 任务 ID (用于更新任务状态)

    Returns:
        PaperProcessingResult with status and details
    """
    paper_id = paper_content.get("arxiv_id", "unknown")
    paper_title = paper_content.get("title", "")
    logger.info(f"Processing paper: {paper_id}")

    result = PaperProcessingResult(
        arxiv_id=paper_id,
        title=paper_title[:100] if paper_title else "",
        status=PaperProcessingStatus.PROCESSING
    )

    try:
        # Step 1: 重建 PaperContent
        content = PaperContent(
            arxiv_id=paper_content["arxiv_id"],
            title=paper_content["title"],
            authors=paper_content["authors"],
            published_date=paper_content["published_date"],
            text_content=paper_content["text_content"],
            html_url=paper_content["html_url"],
            pdf_path=paper_content.get("pdf_path"),  # 可选字段
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
            result.status = PaperProcessingStatus.FAILED
            result.message = "LLM extraction failed after all retries"
            return result

        # Step 3: 检查领域相关性
        if not extraction.is_relevant_to_domain:
            logger.info(
                f"Paper {paper_id}: Domain gatekeeper rejected - "
                f"not in SRE/cloud-native/AIOps domain"
            )
            result.status = PaperProcessingStatus.SKIPPED
            result.message = "Domain not relevant (filtered by LLM)"
            result.is_relevant = False
            return result

        if extraction.extraction_data is None:
            logger.warning(
                f"Paper {paper_id}: is_relevant_to_domain but extraction_data is missing"
            )
            result.status = PaperProcessingStatus.FAILED
            result.message = "LLM omitted extraction_data for a domain-relevant paper"
            result.is_relevant = True
            return result

        # Step 4: 写入 Neo4j (异步)
        logger.info(f"Paper {paper_id}: Upserting to Neo4j graph...")
        upsert_success = await neo4j_client.upsert_paper_graph(extraction)

        if not upsert_success:
            logger.error(f"Paper {paper_id}: Neo4j upsert failed")
            result.status = PaperProcessingStatus.FAILED
            result.message = "Neo4j upsert failed"
            return result

        logger.info(f"Paper {paper_id}: Successfully processed")
        result.status = PaperProcessingStatus.SUCCESS
        result.method_name = extraction.extraction_data.proposed_method.name
        result.is_relevant = True
        result.message = "Successfully processed and stored"
        return result

    except Exception as e:
        logger.error(f"Paper {paper_id}: Processing failed - {e}")
        result.status = PaperProcessingStatus.FAILED
        result.message = str(e)
        return result


async def _execute_task_pipeline(
    task_id: str,
    query: str,
    domain_preset: str,
    max_results: int
) -> None:
    """
    执行完整的任务流水线 (带状态追踪和暂停/取消支持).

    Args:
        task_id: 任务 ID
        query: arXiv 搜索查询
        domain_preset: 领域预设
        max_results: 最大论文数
    """
    logger.info(f"Starting task {task_id}: query='{query}', domain='{domain_preset}'")

    try:
        # 连接任务管理器
        await task_manager.connect()

        # 标记任务为运行中
        await task_manager.start_task(task_id)

        # 抓取论文 (使用领域预设优化查询)
        papers = await arxiv_radar.fetch_recent_papers(
            query=query,
            max_results=max_results,
            domain_preset=domain_preset
        )

        if not papers:
            logger.warning(f"Task {task_id}: No papers found")
            await task_manager.complete_task(task_id)
            return

        # 更新总论文数
        await task_manager.update_progress(task_id, total=len(papers))

        # 处理每篇论文
        for i, paper in enumerate(papers):
            # 检查取消信号
            if await task_manager.is_cancelled(task_id):
                logger.info(f"Task {task_id}: Cancelled by user")
                await task_manager.clear_cancel_signal(task_id)
                return

            # 检查暂停信号 (阻塞直到恢复或取消)
            if await task_manager.is_paused(task_id):
                resumed = await task_manager.wait_while_paused(task_id)
                if not resumed:
                    logger.info(f"Task {task_id}: Cancelled while paused")
                    return

            # 更新当前处理论文
            await task_manager.update_progress(
                task_id,
                current_paper_id=paper.arxiv_id,
                current_paper_title=paper.title[:50] if paper.title else ""
            )

            # 处理论文
            content_dict = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors,
                "published_date": paper.published_date,
                "text_content": paper.text_content,
                "html_url": paper.html_url,
            }

            result = await _process_paper_async(content_dict, task_id)

            # 更新任务结果
            await task_manager.add_paper_result(task_id, result)

            logger.info(f"Task {task_id}: Paper {paper.arxiv_id} - {result.status}")

        # 任务完成
        await task_manager.complete_task(task_id)
        logger.info(f"Task {task_id}: Completed successfully")

    except Exception as e:
        logger.error(f"Task {task_id}: Failed with error - {e}")
        await task_manager.fail_task(task_id, str(e))

    finally:
        await task_manager.close()


# =============================================================================
# Celery Task 注册
# =============================================================================

def get_process_paper_task():
    """获取 process_paper_task 函数 (Celery Task 或同步回退)."""
    if get_celery_app() is not None:
        return process_paper_task
    return _process_paper_async


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="process_paper_task",
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
        return _run_async(_process_paper_async(paper_content))
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise self.retry(exc=e)


# =============================================================================
# 同步回退模式 (Redis 不可用时使用)
# =============================================================================

def trigger_pipeline_sync(topic_query: str, max_results: int = 10, domain_preset: str = "sre") -> dict:
    """
    同步回退: 流水线触发 (Redis 不可用时)。

    允许在没有 Redis/Celery 基础设施的情况下进行本地调试。

    Args:
        topic_query: arXiv 搜索查询
        max_results: 最大论文数量
        domain_preset: 领域预设

    Returns:
        Dict with processing results
    """
    logger.info(f"[SYNC MODE] Processing pipeline: query='{topic_query}', domain='{domain_preset}', max_results={max_results}")

    async def _run():
        # Fetch papers
        papers = await arxiv_radar.fetch_recent_papers(topic_query, max_results, domain_preset)
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
            logger.debug(f"[SYNC MODE] Processed paper {paper.arxiv_id}: {result.status}")

        return results

    # Run async code in event loop
    results = _run_async(_run())

    success_count = sum(1 for r in results if r.status == PaperProcessingStatus.SUCCESS)
    logger.info(f"[SYNC MODE] Pipeline complete: {success_count}/{len(results)} succeeded")

    return {
        "status": "sync_completed",
        "mode": "synchronous_fallback",
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": [r.model_dump() for r in results]
    }

async def trigger_pipeline_sync_async(topic_query: str, max_results: int = 10, domain_preset: str = "sre") -> dict:
    """
    同步回退（异步版本）: 供 FastAPI 这类已有事件循环的场景使用。
    """
    logger.info(f"[SYNC MODE][ASYNC] Processing pipeline: query='{topic_query}', domain='{domain_preset}', max_results={max_results}")

    papers = await arxiv_radar.fetch_recent_papers(topic_query, max_results, domain_preset)
    logger.info(f"[SYNC MODE][ASYNC] Fetched {len(papers)} papers")

    results = []
    for paper in papers:
        content_dict = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "published_date": paper.published_date,
            "text_content": paper.text_content,
            "html_url": paper.html_url,
        }
        result = await _process_paper_async(content_dict)
        results.append(result)
        logger.debug(f"[SYNC MODE][ASYNC] Processed paper {paper.arxiv_id}: {result.status}")

    success_count = sum(1 for r in results if r.status == PaperProcessingStatus.SUCCESS)
    logger.info(f"[SYNC MODE][ASYNC] Pipeline complete: {success_count}/{len(results)} succeeded")

    return {
        "status": "sync_completed",
        "mode": "synchronous_fallback_async",
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": [r.model_dump() for r in results],
    }


# =============================================================================
# 流水线触发入口
# =============================================================================

async def trigger_pipeline_task_async(
    topic_query: str,
    max_results: int = 10,
    domain_preset: str = "sre",
    task_id: str = None
) -> dict:
    """
    触发流水线（异步版本）.

    给 FastAPI/Async 场景使用，避免在已有事件循环中调用 run_until_complete。
    """
    celery_app = get_celery_app()

    if celery_app is None:
        return await trigger_pipeline_sync_async(topic_query, max_results, domain_preset)

    logger.info(f"Triggering pipeline via Celery: query='{topic_query}', domain='{domain_preset}', max_results={max_results}")

    papers = await arxiv_radar.fetch_recent_papers(topic_query, max_results, domain_preset)
    logger.info(f"Fetched {len(papers)} new papers")

    task_func = get_process_paper_task()

    task_ids = []
    for paper in papers:
        content_dict = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "published_date": paper.published_date,
            "text_content": paper.text_content,
            "html_url": paper.html_url,
        }

        if hasattr(task_func, "delay"):
            task = task_func.delay(content_dict)
            task_ids.append(task.id)
            logger.debug(f"Dispatched task {task.id} for paper {paper.arxiv_id}")
        else:
            # fallback (shouldn't happen here, but keep behavior consistent)
            result = await task_func(content_dict)
            logger.debug(f"Async processing for paper {paper.arxiv_id}: {result.status}")

    logger.info(f"Pipeline triggered: {len(task_ids)} tasks dispatched")
    return {"status": "dispatched", "task_count": len(task_ids), "task_ids": task_ids}


def trigger_pipeline_task(topic_query: str, max_results: int = 10, domain_preset: str = "sre") -> dict:
    """
    触发流水线.

    这是 API 调用的主入口。
    如果 Redis 不可用，自动回退到同步模式。

    Args:
        topic_query: arXiv 搜索查询
        max_results: 最大论文数量
        domain_preset: 领域预设

    Returns:
        Dict with task IDs and status
    """
    # 同步封装：给非 async 场景使用（例如 CLI / 同步调用）
    try:
        asyncio.get_running_loop()
        # 已有事件循环运行中：请改用 trigger_pipeline_task_async
        raise RuntimeError("trigger_pipeline_task called inside a running event loop; use trigger_pipeline_task_async")
    except RuntimeError as e:
        if "no running event loop" not in str(e).lower():
            raise

    return _run_async(trigger_pipeline_task_async(topic_query, max_results, domain_preset))


# =============================================================================
# 任务执行入口 (供 TaskManager 使用)
# =============================================================================

async def execute_task_pipeline_async(
    task_id: str,
    query: str,
    domain_preset: str,
    max_results: int
) -> None:
    """
    执行任务流水线 (由 task_routes.py 的 create_task 调用).

    Args:
        task_id: 任务 ID
        query: arXiv 搜索查询
        domain_preset: 领域预设
        max_results: 最大论文数
    """
    await _execute_task_pipeline(task_id, query, domain_preset, max_results)


# =============================================================================
# Celery 任务包装器 (用于后台 Worker)
# =============================================================================

@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="run_task_pipeline_task",
)
def run_task_pipeline_task(
    self,
    task_id: str,
    query: str,
    domain_preset: str,
    max_results: int
) -> dict:
    """
    Celery Task: 在后台 Worker 中执行完整任务流水线.

    Args:
        task_id: 任务 ID
        query: arXiv 搜索查询
        domain_preset: 领域预设
        max_results: 最大论文数

    Returns:
        Dict with status
    """
    try:
        logger.info(f"Celery task started: task_id={task_id}")
        _run_async(execute_task_pipeline_async(task_id, query, domain_preset, max_results))
        return {"status": "completed", "task_id": task_id}
    except Exception as e:
        logger.error(f"Celery task failed: task_id={task_id}, error={e}")
        raise self.retry(exc=e)
