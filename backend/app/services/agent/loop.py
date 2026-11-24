"""Agent loop orchestrating LLM calls with HTTP MCP tool invocation (Task 6).

Design:
- The caller resolves and injects a *minimal* set of tool definitions
  (``{tool_name: ToolRuntime}``) — only the user's skill-bound, currently
  connected tools. The loop never discovers tools on its own.
- Before each outbound call the host validates the model's arguments against
  the tool's ``inputSchema``; invalid args or unknown tools are ``rejected``
  and the server is never called (BE-08, SEC-11).
- Tool results are sanitized (instruction lines dropped, truncated) before
  being appended as ``tool`` role messages — results are data, never system
  instructions (AI-08).
- Two limits bound the loop: ``agent_max_tool_iterations`` (rounds) and
  ``agent_max_total_tool_calls`` (cumulative). Hitting either stops calling
  tools and falls back to a final tool-free model call, then a degradation
  message (AI-10).
- Each call is persisted via ``ToolCallRecordService`` (success/rejected/error).
- :meth:`events` streams each resolved call live so SSE layers can push tool
  events (and the final ``meta``) before the answer body (Task 7).
"""

from __future__ import annotations

import json
import logging
import time

from app.core.config import settings
from app.models.tool_call_record import ToolCallResult
from app.services.agent.http_client import call_mcp_tool
from app.services.agent.param_validate import validate_tool_args
from app.services.agent.resolver import ToolRuntime
from app.services.agent.result_check import sanitize_tool_result
from app.services.model import ModelError, chat_completion_with_tools

logger = logging.getLogger("agent.loop")

_STATUS_MAP = {
    "success": ToolCallResult.SUCCESS,
    "rejected": ToolCallResult.REJECTED,
    "error": ToolCallResult.ERROR,
}


class AgentLoop:
    """Drive a model through a bounded tool-calling loop."""

    def __init__(
        self,
        tools: dict[str, ToolRuntime],
        capability: str = "agent",
        owner_id: str | None = None,
        conversation_id: str | None = None,
        triggered_by: str | None = None,
        record_service=None,
    ) -> None:
        self._tools = tools or {}
        self._capability = capability
        self._owner_id = owner_id
        self._conversation_id = conversation_id
        self._triggered_by = triggered_by or owner_id
        self._record = record_service
        self._max_iterations = settings.agent_max_tool_iterations
        self._max_total_calls = settings.agent_max_total_tool_calls

    def _openai_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": rt.description,
                    "parameters": rt.input_schema or {},
                },
            }
            for name, rt in self._tools.items()
        ]

    async def _write_record(
        self, name: str, server_name: str | None, status: str,
        round_index: int, duration_ms: int,
    ) -> None:
        if self._record is None or self._owner_id is None:
            return
        await self._record.record_call(
            owner_id=self._owner_id,
            tool_name=name,
            server_name=server_name,
            result=_STATUS_MAP[status],
            triggered_by=self._triggered_by,
            conversation_id=self._conversation_id,
            round_index=round_index,
            duration_ms=duration_ms,
        )

    async def events(self, system_prompt: str, user_content: str):
        """Stream loop events, then one terminal ``result`` event.

        Yields dicts:
        * ``{"type": "tool", "tool", "name", "server", "status",
          "duration_ms"}`` for each resolved tool call (incremental, before
          the body).
        * ``{"type": "result", "content", "tool_calls", "time_context"}`` once
          at the end.

        Raises ``ModelError`` if the model itself fails (the same contract as
        :meth:`run`).
        """
        tools_schema = self._openai_tools()
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        call_log: list[dict] = []
        final_content = ""
        time_context = None
        total_calls = 0
        halted = False

        for iteration in range(self._max_iterations):
            try:
                message = await chat_completion_with_tools(
                    messages=messages,
                    tools=tools_schema if tools_schema else None,
                    capability=self._capability,
                )
            except ModelError:
                logger.warning(
                    "agent loop LLM error: capability=%s", self._capability
                )
                raise

            time_context = message.get("time_context") or time_context
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                final_content = message.get("content") or ""
                break

            messages.append(message)
            for tc in tool_calls:
                total_calls += 1
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                try:
                    args = (
                        json.loads(args_raw)
                        if isinstance(args_raw, str)
                        else args_raw
                    )
                except (json.JSONDecodeError, TypeError):
                    args = {}

                started = time.monotonic()
                rt = self._tools.get(name)
                if rt is None:
                    status = "rejected"
                    result_text = json.dumps(
                        {"error": f"tool '{name}' is not available"},
                        ensure_ascii=False,
                    )
                else:
                    ok, reason = validate_tool_args(rt.input_schema, args)
                    if not ok:
                        status = "rejected"
                        result_text = json.dumps(
                            {"error": f"invalid arguments: {reason}"},
                            ensure_ascii=False,
                        )
                    else:
                        text, is_error = await call_mcp_tool(
                            rt.base_url, rt.token, name, args
                        )
                        text = sanitize_tool_result(text)
                        status = "success" if not is_error else "error"
                        result_text = text or json.dumps(
                            {"error": f"tool '{name}' returned no result"},
                            ensure_ascii=False,
                        )

                duration_ms = round((time.monotonic() - started) * 1000)
                server_name = rt.server_name if rt else None
                await self._write_record(
                    name, server_name, status, iteration, duration_ms
                )
                logger.info(
                    "agent_tool_call",
                    tool=name,
                    capability=self._capability,
                    status=status,
                    duration_ms=duration_ms,
                    iteration=iteration,
                )
                ref = f"{name}@{server_name}" if server_name else name
                entry = {
                    "tool": ref,
                    "name": name,
                    "server": server_name,
                    "status": status,
                    "duration_ms": duration_ms,
                }
                call_log.append(entry)
                yield {"type": "tool", **entry}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_text,
                    }
                )
                if total_calls >= self._max_total_calls:
                    halted = True
                    break
            if halted:
                break

        # No final answer yet: synthesize one with a tool-free model call so the
        # user gets an answer built from collected tool results (graceful).
        if not final_content:
            try:
                message = await chat_completion_with_tools(
                    messages=messages, tools=None, capability=self._capability
                )
                final_content = message.get("content") or ""
                time_context = message.get("time_context") or time_context
            except ModelError:
                logger.warning(
                    "agent loop final synthesis failed: capability=%s",
                    self._capability,
                )

        if not final_content:
            final_content = "已达到工具调用上限，请简化问题后重试。"

        yield {
            "type": "result",
            "content": final_content,
            "tool_calls": call_log,
            "time_context": time_context,
        }

    async def run(self, system_prompt: str, user_content: str) -> dict:
        """Collect :meth:`events` and return the final result dict.

        Kept for non-streaming callers and tests; returns the same shape as
        before the streaming refactor.
        """
        result: dict = {}
        async for evt in self.events(system_prompt, user_content):
            if evt["type"] == "result":
                result = evt
        return {
            "content": result.get("content", ""),
            "tool_calls": result.get("tool_calls", []),
            "time_context": result.get("time_context"),
        }
