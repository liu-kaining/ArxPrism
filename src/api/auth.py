"""
JWT 鉴权与角色依赖：Supabase access token + public.profiles。
- 旧版：HS256 + SUPABASE_JWT_SECRET（python-jose）
- 新版：RS256/ES256，公钥自 {SUPABASE_URL}/auth/v1/certs（PyJWT + PyJWKClient）
可选 AUTH_DISABLED 开发旁路；管理员可额外接受旧版 X-ArxPrism-Admin-Token（无需 Bearer）。
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Annotated, Any, Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

import jwt as pyjwt
from jwt import PyJWKClient

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


def _jwt_header_unverified(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        pad = "=" * (-len(parts[0]) % 4)
        raw = base64.urlsafe_b64decode(parts[0] + pad)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _decode_supabase_jwt_hs256(token: str, secret: str) -> dict:
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )


def _decode_supabase_jwt_jwks(token: str, alg: str) -> dict:
    """Supabase 新版 JWT 多为 RS256/ES256；JWKS 在 /auth/v1/certs（部分项目需带 anon key，否则 401）。"""
    base = (settings.supabase_url or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="Server misconfigured: SUPABASE_URL is empty (required for JWKS / asymmetric JWT)",
        )
    anon = (settings.supabase_anon_key or "").strip()
    if not anon:
        raise HTTPException(
            status_code=503,
            detail="Server misconfigured: SUPABASE_ANON_KEY is empty (required to fetch /auth/v1/certs for RS256/ES256)",
        )
    jwks_headers = {
        "apikey": anon,
        "Authorization": f"Bearer {anon}",
    }
    jwks_url = f"{base}/auth/v1/certs"
    alt_url = f"{base}/auth/v1/.well-known/jwks.json"
    last_err: Optional[Exception] = None
    signing_key = None
    for url in (jwks_url, alt_url):
        try:
            client = PyJWKClient(url, headers=jwks_headers)
            signing_key = client.get_signing_key_from_jwt(token)
            break
        except Exception as e:
            last_err = e
    if signing_key is None:
        raise HTTPException(
            status_code=503,
            detail=f"Could not load Supabase JWKS (tried /auth/v1/certs and /.well-known/jwks.json): {last_err}",
        ) from last_err
    try:
        return pyjwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except pyjwt.InvalidAudienceError:
        return pyjwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            options={"verify_aud": False},
        )
    except pyjwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


def _decode_supabase_jwt(token: str) -> dict:
    header = _jwt_header_unverified(token)
    alg = (header.get("alg") or "HS256").upper()

    if alg == "HS256":
        secret = (settings.supabase_jwt_secret or "").strip()
        if not secret:
            raise HTTPException(
                status_code=503,
                detail="Server misconfigured: SUPABASE_JWT_SECRET is empty",
            )
        try:
            return _decode_supabase_jwt_hs256(token, secret)
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    if alg in ("RS256", "ES256"):
        return _decode_supabase_jwt_jwks(token, alg)

    raise HTTPException(
        status_code=401,
        detail=f"Invalid token: The specified alg value is not allowed ({alg})",
    )


async def _profile_to_user(user_id: str, email: Optional[str]) -> CurrentUser:
    row = await supabase_backend.get_profile_row(user_id)
    if not row:
        raise HTTPException(
            status_code=403,
            detail="User profile missing; ensure Supabase trigger handle_new_user is installed",
        )
    raw_role = row.get("role")
    if raw_role is None:
        norm_role = "user"
    else:
        norm_role = str(raw_role).strip().lower() or "user"

    return CurrentUser(
        id=user_id,
        email=email,
        role=norm_role,
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
    raw_sub = payload.get("sub") if payload.get("sub") is not None else payload.get("user_id")
    sub = str(raw_sub).strip() if raw_sub is not None else ""
    if not sub:
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
