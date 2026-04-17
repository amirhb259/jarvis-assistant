from __future__ import annotations

from copy import deepcopy

from app.core.models import CommandResult


class ConversationContextService:
    def __init__(self) -> None:
        self._context: dict[str, object] = {
            "last_intent": "",
            "last_target": "",
            "last_entities": [],
            "last_selected_tool": "",
            "last_plan_summary": "",
            "last_app": "",
            "last_website": "",
            "last_response": "",
            "last_clarification": "",
            "last_created_path": "",
            "last_window_title": "",
            "active_workflow": {},
            "recent_turns": [],
        }

    def snapshot(self) -> dict[str, object]:
        return deepcopy(self._context)

    def record_user_turn(self, text: str) -> None:
        self._context["recent_turns"] = (self._context.get("recent_turns", []) + [{"role": "user", "text": text}])[-8:]

    def update_from_result(self, result: CommandResult) -> None:
        self._context["last_intent"] = result.intent
        self._context["last_target"] = result.understood_target
        self._context["last_entities"] = deepcopy(result.extracted_entities)
        self._context["last_selected_tool"] = result.selected_tool
        self._context["last_plan_summary"] = result.plan_summary
        self._context["last_response"] = result.message
        self._context["last_clarification"] = (
            result.message if result.execution_status == "needs_clarification" or result.requires_confirmation else ""
        )
        if result.intent == "open_app":
            self._context["last_app"] = result.understood_target
            self._context["last_window_title"] = result.understood_target
        if result.intent in {"open_website", "search_google", "search_youtube"}:
            self._context["last_website"] = result.understood_target
        if result.intent in {"create_folder", "create_file"} and result.details:
            self._context["last_created_path"] = result.details.splitlines()[0]
        if result.intent == "focus_window":
            self._context["last_window_title"] = result.understood_target

        self._context["active_workflow"] = {
            "intent": result.intent,
            "target": result.understood_target,
            "tool": result.selected_tool,
            "plan_summary": result.plan_summary,
            "status": result.execution_status,
        }
        self._context["recent_turns"] = (
            self._context.get("recent_turns", [])
            + [{"role": "assistant", "text": result.message, "intent": result.intent, "target": result.understood_target}]
        )[-8:]
