"""
ArxPrism Task API Routes

任务管理相关的 API 端点。
支持任务的创建、查询、暂停、恢复、取消等操作。

Reference: ARCHITECTURE.md Section 5 (扩展)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.models.schemas import APIResponse
from src.models.task_models import (
    Task,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskSummary,
    TaskStatus,
    DomainPreset,
    list_domain_presets,
)
from src.services.task_manager import task_manager, get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# =============================================================================
# 领域预设 API
# =============================================================================

@router.get("/presets", response_model=APIResponse)
async def get_domain_presets() -> APIResponse:
    """
    获取所有可用的领域预设.

    Returns:
        领域预设列表
    """
    presets = list_domain_presets()
    return APIResponse(
        code=200,
        message="success",
        data={
            "presets": [preset.model_dump() for preset in presets]
        }
    )


# =============================================================================
# 任务 CRUD API
# =============================================================================

@router.post("", response_model=APIResponse, status_code=201)
async def create_task(request: TaskCreateRequest) -> APIResponse:
    """
    创建新任务.

    创建任务后会立即返回 task_id，任务在后台异步执行。

    Payload:
        - query: arXiv 搜索查询
        - domain_preset: 领域预设 (sre/aiops/microservices/distributed/cloudnative/custom)
        - max_results: 最大论文数 (1-100)

    Returns:
        HTTP 201 Created with task_id
    """
    logger.info(f"Creating task: query='{request.query}', domain='{request.domain_preset}'")

    try:
        # 获取任务管理器
        manager = await get_task_manager()

        # 创建任务
        task = await manager.create_task(
            query=request.query,
            domain_preset=request.domain_preset,
            max_results=request.max_results
        )

        # 触发后台任务执行
        from src.worker.tasks import execute_task_pipeline_async
        import asyncio
        asyncio.create_task(
            execute_task_pipeline_async(
                task_id=task.task_id,
                query=request.query,
                domain_preset=request.domain_preset,
                max_results=request.max_results
            )
        )

        return APIResponse(
            code=201,
            message="Task created and started",
            data=TaskCreateResponse(
                task_id=task.task_id,
                status=task.status,
                message="Task created and pending execution"
            ).model_dump()
        )

    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"Task creation failed: {str(e)}")


@router.get("", response_model=APIResponse)
async def list_tasks(
    status: Optional[TaskStatus] = Query(None, description="按状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制")
) -> APIResponse:
    """
    获取任务列表.

    按创建时间倒序返回最近的任务列表。

    Query Parameters:
        - status: 可选，按状态筛选
        - limit: 返回数量限制 (默认 20)

    Returns:
        任务列表
    """
    try:
        manager = await get_task_manager()
        tasks = await manager.list_recent_tasks(limit=limit)

        # 按状态筛选
        if status is not None:
            tasks = [t for t in tasks if t.status == status]

        # 转换为摘要格式
        summaries = [
            TaskSummary(
                task_id=t.task_id,
                status=t.status,
                query=t.query,
                domain_preset=t.domain_preset,
                progress=t.progress,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            for t in tasks
        ]

        return APIResponse(
            code=200,
            message="success",
            data={
                "tasks": [s.model_dump() for s in summaries],
                "total": len(summaries)
            }
        )

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.get("/{task_id}", response_model=APIResponse)
async def get_task(task_id: str) -> APIResponse:
    """
    获取任务详情.

    返回任务的完整信息，包括进度和各论文处理结果。

    Path Parameters:
        - task_id: 任务 ID

    Returns:
        任务详情
    """
    logger.info(f"Getting task: {task_id}")

    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return APIResponse(
            code=200,
            message="success",
            data=task.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


# =============================================================================
# 任务控制 API
# =============================================================================

@router.post("/{task_id}/pause", response_model=APIResponse)
async def pause_task(task_id: str) -> APIResponse:
    """
    暂停任务.

    仅运行中的任务可以暂停。暂停后任务会保留当前进度，
    可以通过 /resume 恢复执行。

    Path Parameters:
        - task_id: 任务 ID

    Returns:
        操作结果
    """
    logger.info(f"Pausing task: {task_id}")

    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        success = await manager.pause_task(task_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Task cannot be paused (current status: {task.status})"
            )

        return APIResponse(
            code=200,
            message="Task paused successfully",
            data={"task_id": task_id, "status": "paused"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause task: {str(e)}")


@router.post("/{task_id}/resume", response_model=APIResponse)
async def resume_task(task_id: str) -> APIResponse:
    """
    恢复任务.

    仅已暂停的任务可以恢复。

    Path Parameters:
        - task_id: 任务 ID

    Returns:
        操作结果
    """
    logger.info(f"Resuming task: {task_id}")

    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        success = await manager.resume_task(task_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Task cannot be resumed (current status: {task.status})"
            )

        return APIResponse(
            code=200,
            message="Task resumed successfully",
            data={"task_id": task_id, "status": "running"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume task: {str(e)}")


@router.post("/{task_id}/cancel", response_model=APIResponse)
async def cancel_task(task_id: str) -> APIResponse:
    """
    取消任务.

    仅等待中、运行中或已暂停的任务可以取消。
    取消后任务不可恢复。

    Path Parameters:
        - task_id: 任务 ID

    Returns:
        操作结果
    """
    logger.info(f"Cancelling task: {task_id}")

    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        success = await manager.cancel_task(task_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Task cannot be cancelled (current status: {task.status})"
            )

        return APIResponse(
            code=200,
            message="Task cancelled successfully",
            data={"task_id": task_id, "status": "cancelled"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


@router.post("/{task_id}/retry", response_model=APIResponse)
async def retry_task(task_id: str) -> APIResponse:
    """
    重试失败的任务.

    仅已失败的任务可以重试。重试会创建新任务。

    Path Parameters:
        - task_id: 任务 ID

    Returns:
        新任务信息
    """
    logger.info(f"Retrying task: {task_id}")

    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if task.status != TaskStatus.FAILED:
            raise HTTPException(
                status_code=400,
                detail=f"Only failed tasks can be retried (current status: {task.status})"
            )

        # 创建新任务
        new_task = await manager.create_task(
            query=task.query,
            domain_preset=task.domain_preset,
            max_results=task.max_results
        )

        return APIResponse(
            code=200,
            message="Task retry initiated",
            data={
                "original_task_id": task_id,
                "new_task_id": new_task.task_id,
                "status": new_task.status
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry task: {str(e)}")


# =============================================================================
# 任务进度 API
# =============================================================================

@router.get("/{task_id}/progress", response_model=APIResponse)
async def get_task_progress(task_id: str) -> APIResponse:
    """
    获取任务进度.

    仅返回进度信息，不包括完整的论文处理结果列表。
    适合用于轮询进度更新。

    Path Parameters:
        - task_id: 任务 ID

    Returns:
        进度信息
    """
    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return APIResponse(
            code=200,
            message="success",
            data={
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress.model_dump(),
                "can_pause": task.can_pause,
                "can_resume": task.can_resume,
                "can_cancel": task.can_cancel,
                "can_retry": task.can_retry
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task progress {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")
