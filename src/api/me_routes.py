"""当前登录用户资料（含配额）。"""

from fastapi import APIRouter, Depends

from src.api.auth import CurrentUser, get_current_user
from src.models.auth_models import MeResponse, ProfilePublic
from src.models.schemas import APIResponse

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=APIResponse)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> APIResponse:
    return APIResponse(
        code=200,
        message="success",
        data=MeResponse(
            user_id=user.id,
            email=user.email,
            profile=ProfilePublic(
                id=user.id,
                role=user.role,
                quota_limit=user.quota_limit,
                quota_used=user.quota_used,
                is_banned=user.is_banned,
            ),
        ).model_dump(),
    )
