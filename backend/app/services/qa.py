"""Q&A service with RAG retrieval and citation validation (AI-01, AI-03, AI-05)."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.repositories.group import GroupRepository
from app.services.indexer import IndexService
from app.services.model import chat_completion, validate_output

QA_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string"},
                    "chunk_index": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["attachment_id", "chunk_index", "quote"],
            },
        },
    },
    "required": ["answer", "citations"],
}


class QAService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.group_repo = GroupRepository(db)
        self.indexer = IndexService(db)

    async def ask(self, question: str, user_id: str, group_ids: list[str] | None = None):
        if not question or not question.strip():
            raise ApiError(code="PARAM_INVALID", message="empty question")

        # Determine accessible group IDs
        if group_ids is None:
            group_ids = []
        # Filter to only groups the user is a member of
        accessible_groups = []
        for gid in group_ids:
            membership = await self.group_repo.get_membership(gid, user_id)
            if membership:
                accessible_groups.append(gid)

        # Retrieve relevant chunks
        chunks = await self.indexer.search(question, user_id, accessible_groups, limit=5)

        if not chunks:
            return {"answer": "未找到相关资料。", "citations": []}

        # Build context from chunks
        context_parts = []
        for c in chunks:
            context_parts.append(
                f"[doc:{c['attachment_id']}:{c['chunk_index']}] {c['content']}"
            )
        context = "\n\n".join(context_parts)

        prompt = (
            f"基于以下资料回答问题。引用资料时使用 [doc:附件ID:片段序号] 格式。\n\n"
            f"资料：\n{context}\n\n"
            f"问题：{question}\n\n"
            f"请返回JSON：{{\"answer\": \"...\", \"citations\": [{{\"attachment_id\": \"...\", \"chunk_index\": 0, \"quote\": \"...\"}}]}}"
        )

        raw = await chat_completion(prompt)
        # Demo mode: construct a simple response
        if isinstance(raw, dict) and raw.get("demo"):
            # Build answer from top chunk
            top = chunks[0]
            answer = f"根据资料，{top['content'][:100]}..."
            citations = [
                {
                    "attachment_id": top["attachment_id"],
                    "chunk_index": top["chunk_index"],
                    "quote": top["content"][:50],
                }
            ]
        else:
            parsed = validate_output(raw, QA_SCHEMA)
            answer = parsed["answer"]
            citations = parsed["citations"]

        # Validate citations: only keep those that reference retrieved chunks
        valid_chunk_keys = {(c["attachment_id"], c["chunk_index"]) for c in chunks}
        valid_citations = [
            c for c in citations
            if (c.get("attachment_id"), c.get("chunk_index")) in valid_chunk_keys
        ]

        return {"answer": answer, "citations": valid_citations, "sources": chunks}
