"""
管理员接口：用户 / 系统配置 / 状态 + 危险操作（清空、导入导出、图谱自愈）。

默认以 Supabase JWT + profiles.role=admin 鉴权；若配置了 ADMIN_RESET_TOKEN，
可在请求头携带 X-ArxPrism-Admin-Token 作为临时兼容（与 require_admin 一致）。
"""

import json
import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.auth import require_admin
from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.models.auth_models import (
    AdminUserListResponse,
    AdminUserRow,
    SystemSettingsPatchBody,
    SystemSettingsPublic,
    SystemStatusResponse,
    UserPatchBody,
)
from src.models.schemas import APIResponse
from src.services.llm_extractor import llm_extractor
from src.services.runtime_settings import invalidate_runtime_settings_cache
from src.services.supabase_backend import supabase_backend
from src.services.task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class ClearAllDataRequest(BaseModel):
    confirm: Literal["DELETE_ALL"]


# =============================================================================
# 用户与系统配置
# =============================================================================


@router.get("/users", response_model=APIResponse)
async def list_admin_users() -> APIResponse:
    """合并 GoTrue 用户与 profiles（配额 / 角色 / 封禁）。"""
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    auth_users = await supabase_backend.admin_list_auth_users()
    profiles = await supabase_backend.list_all_profiles()
    pmap = {str(p.get("id")): p for p in profiles if p.get("id")}

    rows: list[AdminUserRow] = []
    for u in auth_users:
        uid = str(u.get("id") or "")
        if not uid:
            continue
        prof = pmap.get(uid, {})
        rows.append(
            AdminUserRow(
                id=uid,
                email=u.get("email"),
                created_at=u.get("created_at"),
                role=str(prof.get("role") or "user"),
                quota_limit=int(prof.get("quota_limit") or 0),
                quota_used=int(prof.get("quota_used") or 0),
                is_banned=bool(prof.get("is_banned")),
            )
        )

    return APIResponse(
        code=200,
        message="success",
        data=AdminUserListResponse(users=rows).model_dump(),
    )


@router.patch("/users/{user_id}", response_model=APIResponse)
async def patch_admin_user(user_id: str, body: UserPatchBody) -> APIResponse:
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await supabase_backend.patch_profile(user_id, fields)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return APIResponse(code=200, message="success", data={"user_id": user_id})


@router.post("/users/{user_id}/ban", response_model=APIResponse)
async def ban_user(user_id: str) -> APIResponse:
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    ok = await supabase_backend.patch_profile(user_id, {"is_banned": True})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to ban user")
    return APIResponse(code=200, message="success", data={"user_id": user_id})


@router.post("/users/{user_id}/unban", response_model=APIResponse)
async def unban_user(user_id: str) -> APIResponse:
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    ok = await supabase_backend.patch_profile(user_id, {"is_banned": False})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to unban user")
    return APIResponse(code=200, message="success", data={"user_id": user_id})


@router.post("/users/{user_id}/refill-quota", response_model=APIResponse)
async def refill_user_quota(user_id: str) -> APIResponse:
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    ok = await supabase_backend.patch_profile(user_id, {"quota_used": 0})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to refill quota")
    return APIResponse(code=200, message="success", data={"user_id": user_id})


@router.get("/system-settings", response_model=APIResponse)
async def get_system_settings_admin() -> APIResponse:
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    row = await supabase_backend.get_system_settings()
    if not row:
        raise HTTPException(status_code=404, detail="system_settings row missing")
    pub = SystemSettingsPublic(
        triage_threshold=float(row.get("triage_threshold") or 0.5),
        html_first_enabled=bool(row.get("html_first_enabled")),
    )
    return APIResponse(code=200, message="success", data=pub.model_dump())


@router.patch("/system-settings", response_model=APIResponse)
async def patch_system_settings_admin(body: SystemSettingsPatchBody) -> APIResponse:
    if not supabase_backend.configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await supabase_backend.patch_system_settings(fields)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update system_settings")
    invalidate_runtime_settings_cache()
    return APIResponse(code=200, message="success", data=fields)


@router.get("/system-status", response_model=APIResponse)
async def get_system_status() -> APIResponse:
    neo4j_n = 0
    try:
        neo4j_n = await neo4j_client.count_total_nodes()
    except Exception as e:
        logger.warning("system-status neo4j: %s", e)

    qdepth: Optional[int] = None
    try:
        await task_manager.connect()
        qdepth = await task_manager.celery_broker_queue_depth()
    except Exception as e:
        logger.debug("system-status redis: %s", e)

    recent_total = 0
    try:
        _, recent_total = await task_manager.list_recent_tasks_page(
            offset=0, limit=1, status=None, active_only=False, terminal_only=False
        )
    except Exception as e:
        logger.warning("system-status tasks: %s", e)

    data = SystemStatusResponse(
        neo4j_node_count=neo4j_n,
        celery_queue_depth=qdepth,
        recent_tasks_total=recent_total,
    )
    return APIResponse(code=200, message="success", data=data.model_dump())


# =============================================================================
# 危险操作（原接口，去掉独立 Token 校验，统一走 require_admin）
# =============================================================================


@router.post("/clear-all-data", response_model=APIResponse)
async def clear_all_data(body: ClearAllDataRequest) -> APIResponse:
    """
    一键清空：Neo4j 全库节点与关系 + Redis 中 `arxprism:*` 任务相关键。

    不执行 Redis FLUSHDB，以免影响同库 Celery 队列。
    """
    _ = body

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


@router.post("/heal-graph", response_model=APIResponse)
async def heal_graph() -> APIResponse:
    """
    图谱自愈：拉取 Method 名称 → LLM 实体对齐 → 物理融合同义 Method 节点。
    """
    method_names = await neo4j_client.get_all_method_names()
    if not method_names:
        return APIResponse(
            code=200,
            message="success",
            data={
                "method_names_count": 0,
                "clusters_from_llm": 0,
                "clusters_applied": 0,
                "alias_nodes_merged": 0,
                "skipped_clusters": [],
                "llm_error": None,
            },
        )

    known = set(method_names)
    resolution = await llm_extractor.resolve_method_entities(method_names)
    if resolution is None:
        raise HTTPException(
            status_code=502,
            detail="LLM entity resolution failed after retries; no graph changes applied",
        )

    alias_nodes_merged = 0
    clusters_applied = 0
    skipped: list[dict] = []

    for cl in resolution.clusters:
        primary = (cl.primary_name or "").strip()
        raw_aliases = [
            (a or "").strip()
            for a in (cl.aliases or [])
            if isinstance(a, str) and (a or "").strip() and (a or "").strip() != primary
        ]
        aliases = [a for a in raw_aliases if a in known]
        if not primary:
            skipped.append({"reason": "empty_primary"})
            continue
        if primary not in known:
            skipped.append({"reason": "primary_not_in_graph", "primary_name": primary})
            continue
        if not aliases:
            continue
        clusters_applied += 1
        alias_nodes_merged += await neo4j_client.merge_method_nodes(primary, aliases)

    return APIResponse(
        code=200,
        message="success",
        data={
            "method_names_count": len(method_names),
            "clusters_from_llm": len(resolution.clusters),
            "clusters_applied": clusters_applied,
            "alias_nodes_merged": alias_nodes_merged,
            "skipped_clusters": skipped,
            "llm_error": None,
        },
    )


@router.get("/export-graph")
async def export_graph(
    include_embeddings: bool = Query(
        True,
        description="为 false 时不导出 Paper.embedding，文件更小但导入后需重新跑嵌入以使用语义检索",
    ),
) -> Response:
    """下载当前 Neo4j 图 JSON 快照（与 import-graph 配对）。"""
    try:
        snap = await neo4j_client.export_graph_snapshot(
            include_embeddings=include_embeddings
        )
    except Exception as e:
        logger.exception("export-graph failed: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Export failed: {e!s}"
        ) from e
    body = json.dumps(snap, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="arxprism-graph-export.json"'
        },
    )


@router.post("/import-graph", response_model=APIResponse)
async def import_graph(
    file: UploadFile = File(..., description="arxprism-graph-export.json"),
    mode: Literal["merge", "replace"] = Form(
        "merge",
        description="merge：按 MERGE 键合并；replace：先清空 Neo4j 再导入（不清理 Redis）",
    ),
) -> APIResponse:
    """从 JSON 快照恢复图数据。大文件请直接调本接口或使用 Neo4j 官方 dump 工具。"""
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Snapshot root must be a JSON object")

    try:
        stats = await neo4j_client.import_graph_snapshot(
            payload, replace=(mode == "replace")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("import-graph failed: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Import failed: {e!s}"
        ) from e

    return APIResponse(code=200, message="success", data=stats)
