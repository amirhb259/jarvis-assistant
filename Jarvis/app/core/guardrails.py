from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.tool_registry import ToolDefinition


@dataclass
class SafetyDecision:
    allowed: bool = True
    requires_confirmation: bool = False
    safety_flags: list[str] = field(default_factory=list)
    message: str = ""


class Guardrails:
    def __init__(self, config) -> None:
        self.config = config

    def update_config(self, config) -> None:
        self.config = config

    def run_safety_check(
        self,
        tool: ToolDefinition | None,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SafetyDecision:
        decision = SafetyDecision()
        context = context or {}

        if tool is None:
            return SafetyDecision(allowed=False, safety_flags=["unknown_tool"], message="Kein Tool ausgewählt.")

        if tool.dangerous:
            decision.requires_confirmation = True
            decision.safety_flags.append("dangerous_tool")

        if tool.name == "type_text":
            text = str(params.get("text", ""))
            if len(text) > 140:
                decision.requires_confirmation = True
                decision.safety_flags.append("mass_typing")

        if tool.name == "clipboard_write":
            text = str(params.get("text", ""))
            if len(text) > int(self.config.clipboard_max_length):
                decision.allowed = False
                decision.safety_flags.append("clipboard_payload_too_large")
                decision.message = "Der Text für die Zwischenablage überschreitet die konfigurierte Sicherheitsgrenze."
                return decision
            if len(text) > 180:
                decision.requires_confirmation = True
                decision.safety_flags.append("clipboard_mass_write")

        if tool.name == "focus_window":
            decision.safety_flags.append("window_focus")

        if tool.name == "move_mouse":
            distance = abs(int(params.get("distance", 0) or 0))
            if distance > int(self.config.mouse_max_distance):
                decision.allowed = False
                decision.safety_flags.append("mouse_distance_exceeded")
                decision.message = "Die gewünschte Mausbewegung überschreitet die Sicherheitsgrenze."
                return decision
            decision.safety_flags.append("mouse_automation")

        if tool.name == "click_mouse":
            decision.safety_flags.append("mouse_automation")

        if tool.name in {"open_website", "search_google", "search_youtube"}:
            target = str(params.get("target", "") or params.get("query", "")).lower()
            if any(token in target for token in ("paypal", "bank", "login", "signin", "konto")):
                decision.requires_confirmation = True
                decision.safety_flags.append("sensitive_browser_target")

        if tool.name in {"shutdown_pc", "restart_pc", "lock_pc"}:
            decision.requires_confirmation = True
            decision.safety_flags.append("system_control")

        if "last_clarification" in context and context["last_clarification"]:
            decision.safety_flags.append("contextual_follow_up")

        return decision
