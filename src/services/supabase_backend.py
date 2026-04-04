"""
Supabase REST + Auth Admin（service role），供后端鉴权、配额与运营接口使用。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return (settings.supabase_url or "").strip().rstrip("/")


def _service_headers_json() -> Dict[str, str]:
    key = (settings.supabase_service_role_key or "").strip()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


class SupabaseBackend:
    """异步 HTTP 客户端；按需创建，避免未配置 Supabase 时强依赖。"""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    def configured(self) -> bool:
        return bool(_base_url() and (settings.supabase_service_role_key or "").strip())

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_profile_row(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.configured():
            return None
        url = f"{_base_url()}/rest/v1/profiles"
        client = await self._client_get()
        r = await client.get(
            url,
            params={"id": f"eq.{user_id}", "select": "*"},
            headers={**_service_headers_json(), "Accept": "application/json"},
        )
        if r.status_code != 200:
            logger.warning("get_profile_row failed: %s %s", r.status_code, r.text[:200])
            return None
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return None
        return rows[0]

    async def rpc_try_consume_task_quota(self, user_id: str) -> Tuple[bool, Optional[str]]:
        if not self.configured():
            return False, "supabase_not_configured"
        url = f"{_base_url()}/rest/v1/rpc/try_consume_task_quota"
        client = await self._client_get()
        r = await client.post(
            url,
            json={"p_user_id": user_id},
            headers=_service_headers_json(),
        )
        if r.status_code != 200:
            logger.warning("try_consume_task_quota HTTP %s: %s", r.status_code, r.text[:300])
            return False, "rpc_error"
        try:
            data = r.json()
        except Exception:
            return False, "invalid_response"
        if not isinstance(data, dict):
            return False, "invalid_response"
        if data.get("ok") is True:
            return True, None
        return False, str(data.get("reason") or "denied")

    async def rpc_refund_task_quota(self, user_id: str) -> None:
        if not self.configured():
            return
        url = f"{_base_url()}/rest/v1/rpc/refund_task_quota"
        client = await self._client_get()
        r = await client.post(
            url,
            json={"p_user_id": user_id},
            headers=_service_headers_json(),
        )
        if r.status_code not in (200, 204):
            logger.warning("refund_task_quota HTTP %s: %s", r.status_code, r.text[:300])

    async def list_all_profiles(self) -> List[Dict[str, Any]]:
        if not self.configured():
            return []
        url = f"{_base_url()}/rest/v1/profiles"
        client = await self._client_get()
        r = await client.get(
            url,
            params={"select": "*"},
            headers={**_service_headers_json(), "Accept": "application/json"},
        )
        if r.status_code != 200:
            logger.warning("list_all_profiles failed: %s", r.status_code)
            return []
        data = r.json()
        return data if isinstance(data, list) else []

    async def admin_list_auth_users(self) -> List[Dict[str, Any]]:
        """GoTrue admin API：分页拉取全部用户。"""
        if not self.configured():
            return []
        client = await self._client_get()
        headers = _service_headers_json()
        out: List[Dict[str, Any]] = []
        page = 1
        per_page = 200
        while True:
            url = f"{_base_url()}/auth/v1/admin/users"
            r = await client.get(
                url,
                params={"page": page, "per_page": per_page},
                headers=headers,
            )
            if r.status_code != 200:
                logger.warning("admin_list_auth_users failed: %s %s", r.status_code, r.text[:200])
                break
            payload = r.json()
            users = payload.get("users") if isinstance(payload, dict) else None
            if not isinstance(users, list):
                break
            out.extend(users)
            if len(users) < per_page:
                break
            page += 1
        return out

    async def patch_profile(self, user_id: str, fields: Dict[str, Any]) -> bool:
        if not self.configured():
            return False
        url = f"{_base_url()}/rest/v1/profiles"
        client = await self._client_get()
        r = await client.patch(
            url,
            params={"id": f"eq.{user_id}"},
            json=fields,
            headers={**_service_headers_json(), "Prefer": "return=minimal"},
        )
        return r.status_code in (200, 204)

    async def get_system_settings(self) -> Optional[Dict[str, Any]]:
        if not self.configured():
            return None
        url = f"{_base_url()}/rest/v1/system_settings"
        client = await self._client_get()
        r = await client.get(
            url,
            params={"id": "eq.1", "select": "*"},
            headers={**_service_headers_json(), "Accept": "application/json"},
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return None
        return rows[0]

    async def patch_system_settings(self, fields: Dict[str, Any]) -> bool:
        if not self.configured():
            return False
        allowed = {k: v for k, v in fields.items() if k in ("triage_threshold", "html_first_enabled")}
        if not allowed:
            return True
        url = f"{_base_url()}/rest/v1/system_settings"
        client = await self._client_get()
        r = await client.patch(
            url,
            params={"id": "eq.1"},
            json=allowed,
            headers={**_service_headers_json(), "Prefer": "return=minimal"},
        )
        return r.status_code in (200, 204)


supabase_backend = SupabaseBackend()
