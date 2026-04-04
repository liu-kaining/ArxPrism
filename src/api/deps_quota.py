"""
任务配额依赖：与具体 router 解耦，供 task_routes / routes(pipeline) 共用。
"""

from __future__ import annotations

from fastapi import HTTPException

from src.api.auth import CurrentUser
from src.core.config import settings
from src.services.supabase_backend import supabase_backend

# /pipeline/trigger 每篇待发论文预扣 1 点配额，封顶避免单次 RPC 风暴与 LLM 刷爆
PIPELINE_TRIGGER_MAX_QUOTA_UNITS = 30


async def consume_one_task_quota(user: CurrentUser) -> None:
    """创建 / 重试任务前扣 1 点配额（AUTH_DISABLED 时跳过）。"""
    if settings.auth_disabled:
        return
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account banned")
    if not supabase_backend.configured():
        raise HTTPException(
            status_code=503,
            detail="Task quota unavailable: Supabase not configured",
        )
    ok, reason = await supabase_backend.rpc_try_consume_task_quota(user.id)
    if ok:
        return
    if reason == "no_profile":
        raise HTTPException(
            status_code=403,
            detail="User profile missing; run Supabase SQL migration (handle_new_user)",
        )
    if reason == "banned":
        raise HTTPException(status_code=403, detail="Account banned")
    if reason == "quota_exhausted":
        raise HTTPException(
            status_code=402,
            detail="Task quota exhausted; contact an administrator to refill.",
        )
    raise HTTPException(
        status_code=503,
        detail=f"Could not verify task quota: {reason or 'unknown'}",
    )


async def consume_n_task_quotas(user: CurrentUser, n: int) -> None:
    """连续扣 n 次任务配额（用于 legacy pipeline 与 max_results 对齐）。"""
    count = max(0, min(int(n), PIPELINE_TRIGGER_MAX_QUOTA_UNITS))
    for _ in range(count):
        await consume_one_task_quota(user)


async def refund_n_task_quotas(user_id: str, n: int) -> None:
    """pipeline 触发在 dispatch 前失败时回滚已扣配额。"""
    if settings.auth_disabled:
        return
    count = max(0, min(int(n), PIPELINE_TRIGGER_MAX_QUOTA_UNITS))
    for _ in range(count):
        await supabase_backend.rpc_refund_task_quota(user_id)
