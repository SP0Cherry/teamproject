"""Skill endpoints: CRUD with pre-save tool reference validation (AI-09)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.openapi_docs import LOGIN_REQUIRED, responses
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.skill import SkillService, serialize

router = APIRouter(prefix="/skills", tags=["skills"])


class CreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="技能名称")
    capability: str = Field(
        pattern=r"^(qa|notification_extraction)$",
        description="能力标识：qa 或 notification_extraction",
    )
    tool_refs: list[str] = Field(
        default_factory=list,
        description="工具引用列表，格式 `工具名@服务器名`，如 search@web",
    )


class UpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128, description="新名称")
    capability: str | None = Field(
        default=None, pattern=r"^(qa|notification_extraction)$", description="新能力标识"
    )
    tool_refs: list[str] | None = Field(default=None, description="新工具引用列表（传入即替换）")


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.post(
    "",
    summary="创建技能",
    description=(
        "保存前校验 tool_refs：格式合法、服务器属于当前用户且已连接、工具在服务器清单内；"
        f"任一失败返回 BUSINESS_RULE 422。{LOGIN_REQUIRED}"
    ),
    responses=responses(400, 401, 422),
)
async def create_skill(
    body: CreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await SkillService(db).create(
        current_user.id, body.name, body.capability, body.tool_refs
    )
    return success_response(
        data=serialize(skill), message="created", request_id=_rid(request)
    )


@router.get(
    "",
    summary="列出我的技能",
    description=f"仅返回当前用户的技能。{LOGIN_REQUIRED}",
    responses=responses(401),
)
async def list_skills(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skills = await SkillService(db).list(current_user.id)
    return success_response(
        data=[serialize(s) for s in skills], request_id=_rid(request)
    )


@router.get(
    "/{skill_id}",
    summary="获取技能详情",
    description=f"非所有者返回 404，与不存在不可区分。{LOGIN_REQUIRED}",
    responses=responses(401, 404),
)
async def get_skill(
    skill_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await SkillService(db).get(skill_id, current_user.id)
    return success_response(data=serialize(skill), request_id=_rid(request))


@router.patch(
    "/{skill_id}",
    summary="更新技能",
    description=(
        "更新时重新执行保存前三校验；tool_refs 中引用未连接或越权工具时返回 BUSINESS_RULE 422。"
        f"{LOGIN_REQUIRED}"
    ),
    responses=responses(400, 401, 404, 422),
)
async def update_skill(
    skill_id: str,
    body: UpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await SkillService(db).update(
        skill_id, current_user.id, body.name, body.capability, body.tool_refs
    )
    return success_response(
        data=serialize(skill), message="updated", request_id=_rid(request)
    )


@router.delete(
    "/{skill_id}",
    summary="删除技能",
    description=f"非所有者返回 404。{LOGIN_REQUIRED}",
    responses=responses(401, 404),
)
async def delete_skill(
    skill_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await SkillService(db).delete(skill_id, current_user.id)
    return success_response(message="deleted", request_id=_rid(request))
