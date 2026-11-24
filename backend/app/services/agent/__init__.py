"""Agent runtime: HTTP MCP tool-calling loop (stdio removed in Task 6)."""

from app.services.agent.loop import AgentLoop
from app.services.agent.resolver import ToolRuntime, resolve_runtime_tools

__all__ = ["AgentLoop", "ToolRuntime", "resolve_runtime_tools"]
