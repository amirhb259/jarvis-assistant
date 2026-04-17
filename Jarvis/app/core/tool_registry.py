from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


ToolExecutor = Callable[[CommandRequest, ActionContext], CommandResult]
ToolValidator = Callable[[dict[str, Any]], tuple[bool, str]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    executor: ToolExecutor
    validator: ToolValidator | None = None
    dangerous: bool = False
    specialist: str = ""
    intents: tuple[str, ...] = field(default_factory=tuple)

    def validate(self, params: dict[str, Any]) -> tuple[bool, str]:
        if self.validator is None:
            return True, ""
        return self.validator(params)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._intent_to_tool: dict[str, str] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool
        for intent in tool.intents:
            self._intent_to_tool[intent] = tool.name

    def register_handler(
        self,
        tool_name: str,
        handler: CommandHandler,
        input_schema: dict[str, Any],
        specialist: str,
    ) -> None:
        self.register_tool(
            ToolDefinition(
                name=tool_name,
                description=handler.description,
                input_schema=input_schema,
                executor=handler.handle,
                dangerous=handler.dangerous,
                specialist=specialist,
                intents=handler.intents,
            )
        )

    def get(self, tool_name: str) -> ToolDefinition | None:
        return self._tools.get(tool_name)

    def tool_for_intent(self, intent: str) -> ToolDefinition | None:
        tool_name = self._intent_to_tool.get(intent)
        if not tool_name:
            return None
        return self._tools.get(tool_name)

    def all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def summary(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "dangerous": tool.dangerous,
                "specialist": tool.specialist,
                "intents": list(tool.intents),
            }
            for tool in self._tools.values()
        ]
