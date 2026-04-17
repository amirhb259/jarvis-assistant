from __future__ import annotations

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


class FocusWindowHandler(CommandHandler):
    intents = ("focus_window",)
    description = "Bring an existing application window to the foreground."
    examples = (
        "Jarvis, focus Discord",
        "bring the Chrome window to front",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        target = str(request.slots["target"])
        match = context.system_service.focus_window(target, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Focused window '{match.title}'.",
            spoken_text=f"Focusing {match.title}.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target=match.title,
            launch_method="window_focus",
            details=f"process={match.process_name}\nscore={match.score:.2f}",
        )


class ClipboardReadHandler(CommandHandler):
    intents = ("clipboard_read",)
    description = "Read the current clipboard text."
    examples = ("Jarvis, what's in my clipboard?",)

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        text = context.system_service.read_clipboard(context.emit_event)
        preview = text if len(text) <= 280 else f"{text[:280]}..."
        details = preview or "(clipboard is empty)"
        return CommandResult(
            ok=True,
            message="Ich habe den Inhalt der Zwischenablage gelesen.",
            spoken_text="Ich habe den Inhalt der Zwischenablage gelesen.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target="clipboard",
            launch_method="clipboard_read",
            details=details,
        )


class ClipboardWriteHandler(CommandHandler):
    intents = ("clipboard_write",)
    description = "Write text into the clipboard."
    examples = (
        'Jarvis, copy "Hello World" to clipboard',
        "schreib das ins clipboard",
    )
    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        text = str(request.slots["text"])
        written = context.system_service.write_clipboard(text, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Copied {written} characters to the clipboard.",
            spoken_text="Clipboard updated.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target="clipboard",
            launch_method="clipboard_write",
            details=text if len(text) <= 280 else f"{text[:280]}...",
        )
