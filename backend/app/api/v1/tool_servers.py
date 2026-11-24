"""Tool server endpoints: register / list / connect / discover / disconnect.

All endpoints are owner-scoped; non-owners receive 404 indistinguishable from
a missing resource (SEC-02). The stored token is never returned (SEC-08).
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.openapi_docs import LOGIN_REQUIRED, responses
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.tool_server import ToolServerService, serialize

router = APIRouter(prefix="/tool-servers", tags=["tool-servers"])


class CreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="工具服务器名称，所有者内唯一")
    base_url: str = Field(min_length=1, max_length=512, description="HTTP MCP 服务地址，如 http://mcp-server:8090")
    token: str | None = Field(default=None, max_length=1024, description="Bearer 令牌；服务端加密存储，响应永不回传")


class UpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128, description="新名称")
    base_url: str | None = Field(default=None, min_length=1, max_length=512, description="新地址")
    token: str | None = Field(default=None, max_length=1024, description="新令牌（传入即替换）")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.post(
    "",
    summary="登记工具服务器",
    description=f"登记一个 HTTP MCP 工具服务器。令牌加密后存储，响应只返回 has_token。{LOGIN_REQUIRED}",
    responses=responses(400, 401),
)
async def create_server(
    body: CreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await ToolServerService(db).register(
        current_user.id, body.name, body.base_url, body.token
    )
    return success_response(
        data=serialize(server), message="registered", request_id=_request_id(request)
    )


@router.get(
    "",
    summary="列出我的工具服务器",
    description=f"仅返回当前用户登记的服务器。{LOGIN_REQUIRED}",
    responses=responses(401),
)
async def list_servers(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    servers = await ToolServerService(db).list(current_user.id)
    return success_response(
        data=[serialize(s) for s in servers], request_id=_request_id(request)
    )


@router.get(
    "/{server_id}",
    summary="获取工具服务器详情",
    description=f"非所有者返回 404，与不存在不可区分。{LOGIN_REQUIRED}",
    responses=responses(401, 404),
)
async def get_server(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await ToolServerService(db).get(server_id, current_user.id)
    return success_response(data=serialize(server), request_id=_request_id(request))


@router.patch(
    "/{server_id}",
    summary="更新工具服务器",
    description=f"更新名称/地址/令牌。令牌传入即替换并重新加密。{LOGIN_REQUIRED}",
    responses=responses(400, 401, 404),
)
async def update_server(
    server_id: str,
    body: UpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await ToolServerService(db).update(
        server_id, current_user.id, body.name, body.base_url, body.token
    )
    return success_response(
        data=serialize(server), message="updated", request_id=_request_id(request)
    )


@router.delete(
    "/{server_id}",
    summary="删除工具服务器",
    description=f"级联清理归属数据。非所有者返回 404。{LOGIN_REQUIRED}",
    responses=responses(401, 404),
)
async def delete_server(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ToolServerService(db).delete(server_id, current_user.id)
    return success_response(message="deleted", request_id=_request_id(request))


@router.post(
    "/{server_id}/connect",
    summary="连接并发现工具",
    description=(
        "执行 initialize + tools/list 握手。成功则 status=connected 并整体替换 discovered_tools；"
        f"任一步失败则 status=error 并写 last_error，保留旧清单。{LOGIN_REQUIRED}"
    ),
    responses=responses(401, 404),
)
async def connect_server(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await ToolServerService(db).connect(server_id, current_user.id)
    return success_response(
        data=serialize(server), message="connected", request_id=_request_id(request)
    )


@router.post(
    "/{server_id}/disconnect",
    summary="断开工具服务器",
    description=f"置 status=unconnected 并清空 discovered_tools。{LOGIN_REQUIRED}",
    responses=responses(401, 404),
)
async def disconnect_server(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await ToolServerService(db).disconnect(server_id, current_user.id)
    return success_response(
        data=serialize(server), message="disconnected", request_id=_request_id(request)
    )


@router.get(
    "/{server_id}/tools",
    summary="列出服务器发现的工具",
    description=f"返回缓存的 discovered_tools（最近一次成功连接的清单）。{LOGIN_REQUIRED}",
    responses=responses(401, 404),
)
async def list_tools(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await ToolServerService(db).get(server_id, current_user.id)
    return success_response(
        data={"tools": serialize(server)["discovered_tools"]},
        request_id=_request_id(request),
    )
