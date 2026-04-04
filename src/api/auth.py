"""
JWT 鉴权与角色依赖：Supabase HS256 + public.profiles。
可选 AUTH_DISABLED 开发旁路；管理员可额外接受旧版 X-ArxPrism-Admin-Token（无需 Bearer）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from src.core.config import settings
from src.services.supabase_backend import supabase_backend

logger = logging.getLogger(__name__)

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class CurrentUser:
    id: str
    email: Optional[str]
    role: str
    quota_limit: int
    quota_used: int
    is_banned: bool


def _dev_user() -> CurrentUser:
    return CurrentUser(
        id=DEV_USER_ID,
        email="dev@local",
        role="admin",
        quota_limit=999_999,
        quota_used=0,
        is_banned=False,
    )


def _decode_supabase_jwt(token: str) -> dict:
    secret = (settings.supabase_jwt_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Server misconfigured: SUPABASE_JWT_SECRET is empty",
        )
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


async def _profile_to_user(user_id: str, email: Optional[str]) -> CurrentUser:
    row = await supabase_backend.get_profile_row(user_id)
    if not row:
        raise HTTPException(
            status_code=403,
            detail="User profile missing; ensure Supabase trigger handle_new_user is installed",
        )
    return CurrentUser(
        id=user_id,
        email=email,
        role=str(row.get("role") or "user"),
        quota_limit=int(row.get("quota_limit") or 0),
        quota_used=int(row.get("quota_used") or 0),
        is_banned=bool(row.get("is_banned")),
    )


async def _user_from_bearer_authorization(authorization: Optional[str]) -> CurrentUser:
    """从 Authorization: Bearer 解析用户（不含 legacy admin）。"""
    if settings.auth_disabled:
        return _dev_user()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = _decode_supabase_jwt(token)
    sub = payload.get("sub") or payload.get("user_id")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Token missing subject")
    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        email = None

    if not supabase_backend.configured():
        raise HTTPException(
            status_code=503,
            detail="Server misconfigured: Supabase service role not set",
        )

    return await _profile_to_user(sub, email)


async def get_current_user(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> CurrentUser:
    return await _user_from_bearer_authorization(authorization)


async def require_user(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> CurrentUser:
    return await _user_from_bearer_authorization(authorization)


async def require_admin(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
    x_arxprism_admin_token: Annotated[
        Optional[str], Header(alias="X-ArxPrism-Admin-Token")
    ] = None,
) -> CurrentUser:
    """Supabase admin JWT，或（可选）与 ADMIN_RESET_TOKEN 一致的 Header。"""
    legacy = (settings.admin_reset_token or "").strip()
    if legacy and x_arxprism_admin_token == legacy:
        return CurrentUser(
            id="legacy-admin",
            email=None,
            role="admin",
            quota_limit=0,
            quota_used=0,
            is_banned=False,
        )

    user = await _user_from_bearer_authorization(authorization)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
