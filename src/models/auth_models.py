"""Supabase 用户、运营与系统配置相关响应模型。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ProfilePublic(BaseModel):
    id: str
    role: str = "user"
    quota_limit: int = 10
    quota_used: int = 0
    is_banned: bool = False


class MeResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    profile: ProfilePublic


class AdminUserRow(BaseModel):
    id: str
    email: Optional[str] = None
    created_at: Optional[str] = None
    role: str = "user"
    quota_limit: int = 10
    quota_used: int = 0
    is_banned: bool = False


class AdminUserListResponse(BaseModel):
    users: List[AdminUserRow]


class SystemSettingsPublic(BaseModel):
    triage_threshold: float = Field(ge=0.0, le=1.0, default=0.5)
    html_first_enabled: bool = True


class SystemStatusResponse(BaseModel):
    neo4j_node_count: int = 0
    celery_queue_depth: Optional[int] = None
    recent_tasks_total: int = 0


class UserPatchBody(BaseModel):
    role: Optional[Literal["user", "admin"]] = None
    quota_limit: Optional[int] = Field(None, ge=0, le=1_000_000)


class SystemSettingsPatchBody(BaseModel):
    triage_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    html_first_enabled: Optional[bool] = None
