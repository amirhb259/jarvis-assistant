from __future__ import annotations

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


class OpenWebsiteHandler(CommandHandler):
    intents = ("open_website",)
    description = "Open websites in the default browser."
    examples = (
        "Jarvis, open Google",
        "Jarvis, open github.com",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        target = str(request.slots["target"])
        url = context.system_service.open_website(target, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Opening {target}.",
            spoken_text=f"Opening {target}.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target=target,
            launch_method="browser_url",
            details=url,
        )


class SearchHandler(CommandHandler):
    intents = ("search_google", "search_youtube")
    description = "Search Google or YouTube."
    examples = (
        "Jarvis, search Google for Python packaging",
        "Jarvis, search YouTube for lo-fi music",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        query = str(request.slots["query"])
        if request.intent == "search_youtube":
            url = context.system_service.search_youtube(query, context.emit_event)
            return CommandResult(
                ok=True,
                message=f"Searching YouTube for {query}.",
                spoken_text=f"Searching YouTube for {query}.",
                intent=request.intent,
                confidence=request.confidence,
                understood_target=query,
                launch_method="youtube_search",
                details=url,
            )

        url = context.system_service.search_google(query, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Searching Google for {query}.",
            spoken_text=f"Searching Google for {query}.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target=query,
            launch_method="google_search",
            details=url,
        )
