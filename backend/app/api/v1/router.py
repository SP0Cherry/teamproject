from fastapi import APIRouter

from app.api.v1 import attachments, auth, breakdown, groups, health, home, notifications, qa, reminders, skills, tasks, todos, tool_call_records, tool_servers

api_router = APIRouter()
api_router.include_router(attachments.router)
api_router.include_router(auth.router)
api_router.include_router(breakdown.router)
api_router.include_router(groups.router)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(home.router)
api_router.include_router(notifications.router)
api_router.include_router(qa.router)
api_router.include_router(reminders.router)
api_router.include_router(skills.router)
api_router.include_router(tasks.router)
api_router.include_router(todos.router)
api_router.include_router(tool_call_records.router)
api_router.include_router(tool_servers.router)
