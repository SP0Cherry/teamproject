"""Task breakdown suggestion service (AI-06: manual confirmation required)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.repositories.todo import TodoRepository
from app.services.model import chat_completion, validate_output

BREAKDOWN_SCHEMA = {
    "type": "object",
    "properties": {
        "subtasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title"],
            },
        }
    },
    "required": ["subtasks"],
}


class BreakdownService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.todo_repo = TodoRepository(db)

    async def suggest(self, todo_id: str, user_id: str) -> list[dict]:
        """Generate subtask suggestions for a todo (not saved yet)."""
        todo = await self.todo_repo.get(todo_id)
        if todo is None or todo.owner_id != user_id:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")

        prompt = (
            f"将以下任务拆解为子任务，每个子任务有标题和描述。\n"
            f"任务：{todo.title}\n"
            f"描述：{todo.description or '无'}\n\n"
            f"返回JSON：{{\"subtasks\": [{{\"title\": \"...\", \"description\": \"...\"}}]}}"
        )

        raw = await chat_completion(prompt)
        if isinstance(raw, dict) and raw.get("demo"):
            # Demo mode: return canned subtasks
            return [
                {"title": f"{todo.title} - 步骤1", "description": "先做准备工作"},
                {"title": f"{todo.title} - 步骤2", "description": "执行核心任务"},
                {"title": f"{todo.title} - 步骤3", "description": "检查和收尾"},
            ]

        parsed = validate_output(raw, BREAKDOWN_SCHEMA)
        return parsed["subtasks"]

    async def confirm_subtasks(
        self, todo_id: str, user_id: str, selected: list[dict]
    ) -> list[dict]:
        """Save selected subtasks as child todos (manual confirmation, AI-06)."""
        todo = await self.todo_repo.get(todo_id)
        if todo is None or todo.owner_id != user_id:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")

        if not selected:
            raise ApiError(code="PARAM_INVALID", message="no subtasks selected")

        created = []
        for item in selected:
            title = item.get("title", "").strip()
            if not title:
                raise ApiError(code="PARAM_INVALID", message="subtask missing title")
            child = await self.todo_repo.create(
                owner_id=user_id,
                title=title,
                description=item.get("description"),
                due_at=todo.due_at,
                group_id=todo.group_id,
                source_notification_id=todo.source_notification_id,
            )
            created.append({"id": child.id, "title": child.title})
        await self.db.commit()
        return created
