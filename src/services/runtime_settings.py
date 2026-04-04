"""
从 Supabase system_settings 读取运行时开关（带短 TTL 缓存），供 Worker 流水线使用。
未配置或读取失败时使用默认值。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from src.services.supabase_backend import supabase_backend

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 60.0
_cached: Optional[Tuple[float, float, bool]] = None  # (expires, triage_threshold, html_first)
_lock = asyncio.Lock()


@dataclass(frozen=True)
class RuntimePipelineSettings:
    triage_threshold: float = 0.5
    html_first_enabled: bool = True


async def get_runtime_pipeline_settings() -> RuntimePipelineSettings:
    global _cached
    now = time.monotonic()
    async with _lock:
        if _cached and _cached[0] > now:
            return RuntimePipelineSettings(
                triage_threshold=_cached[1],
                html_first_enabled=_cached[2],
            )

    row = None
    try:
        if supabase_backend.configured():
            row = await supabase_backend.get_system_settings()
    except Exception as e:
        logger.warning("runtime_settings fetch failed: %s", e)

    threshold = 0.5
    html_first = True
    if row and isinstance(row, dict):
        try:
            t = row.get("triage_threshold")
            if t is not None:
                threshold = float(t)
                threshold = max(0.0, min(1.0, threshold))
        except (TypeError, ValueError):
            pass
        if row.get("html_first_enabled") is not None:
            html_first = bool(row["html_first_enabled"])

    async with _lock:
        _cached = (now + _CACHE_TTL_SEC, threshold, html_first)

    return RuntimePipelineSettings(
        triage_threshold=threshold,
        html_first_enabled=html_first,
    )


def invalidate_runtime_settings_cache() -> None:
    global _cached
    _cached = None
