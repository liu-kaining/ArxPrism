"""
管理员接口：危险操作（清空业务数据）。

POST /api/v1/admin/clear-all-data
- 请求头: X-ArxPrism-Admin-Token（须与环境变量 ADMIN_RESET_TOKEN 一致）
- JSON body: {"confirm": "DELETE_ALL"}

未配置 ADMIN_RESET_TOKEN 时接口返回 403，避免误部署后暴露清空能力。
"""

import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.models.schemas import APIResponse
from src.services.task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class ClearAllDataRequest(BaseModel):
    confirm: Literal["DELETE_ALL"]


@router.post("/clear-all-data", response_model=APIResponse)
async def clear_all_data(
    body: ClearAllDataRequest,
    x_arxprism_admin_token: Annotated[
        Optional[str], Header(alias="X-ArxPrism-Admin-Token")
    ] = None,
) -> APIResponse:
    """
    一键清空：Neo4j 全库节点与关系 + Redis 中 `arxprism:*` 任务相关键。

    不执行 Redis FLUSHDB，以免影响同库 Celery 队列。
    """
    token = (settings.admin_reset_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=403,
            detail="Admin reset disabled: set ADMIN_RESET_TOKEN in environment",
        )

    if not x_arxprism_admin_token or x_arxprism_admin_token != token:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")

    neo4j_stats: dict
    try:
        neo4j_stats = await neo4j_client.wipe_all_graph_data()
    except Exception as e:
        logger.exception("Neo4j wipe failed: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Neo4j wipe failed: {e!s}"
        ) from e

    redis_deleted = 0
    redis_warning: Optional[str] = None
    try:
        await task_manager.connect()
        redis_deleted = await task_manager.wipe_all_arxprism_keys()
    except Exception as e:
        logger.warning("Redis wipe skipped or failed: %s", e)
        redis_warning = str(e)

    return APIResponse(
        code=200,
        message="success",
        data={
            "neo4j": neo4j_stats,
            "redis_arxprism_keys_deleted": redis_deleted,
            "redis_warning": redis_warning,
        },
    )
