from __future__ import annotations

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


class DateTimeHandler(CommandHandler):
    intents = ("tell_time", "tell_date")
    description = "Tell the time or date."
    examples = (
        "Jarvis, tell me the time",
        "Jarvis, tell me the date",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        if request.intent == "tell_date":
            date_text = context.system_service.get_date_text()
            return CommandResult(
                ok=True,
                message=f"Today is {date_text}.",
                spoken_text=f"Today is {date_text}.",
                intent=request.intent,
                confidence=request.confidence,
            )

        time_text = context.system_service.get_time_text()
        return CommandResult(
            ok=True,
            message=f"The time is {time_text}.",
            spoken_text=f"The time is {time_text}.",
            intent=request.intent,
            confidence=request.confidence,
        )
