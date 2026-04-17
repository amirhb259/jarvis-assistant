from __future__ import annotations

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


class OpenApplicationHandler(CommandHandler):
    intents = ("open_app",)
    description = "Open desktop applications."
    examples = (
        "Jarvis, open Discord",
        "Jarvis, open VS Code",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        target = str(request.slots["target"])
        launch_result = context.app_launcher.launch_app(target, context.emit_event)
        if not launch_result.ok:
            details = launch_result.details
            if launch_result.suggestions:
                details = f"{details}\nSuggestions: {', '.join(launch_result.suggestions)}".strip()
            return CommandResult(
                ok=False,
                message=launch_result.message,
                spoken_text=launch_result.message,
                intent=request.intent,
                confidence=request.confidence,
                understood_target=target,
                launch_method=launch_result.launch_method,
                suggestions=launch_result.suggestions,
                details=details,
            )

        return CommandResult(
            ok=True,
            message=launch_result.message,
            spoken_text=f"Opening {launch_result.resolved_name or target}.",
            intent=request.intent,
            confidence=launch_result.confidence or request.confidence,
            understood_target=launch_result.resolved_name or target,
            launch_method=launch_result.launch_method,
            suggestions=launch_result.suggestions,
            details="\n".join(
                item
                for item in (
                    launch_result.launch_target,
                    launch_result.details,
                )
                if item
            ),
        )
