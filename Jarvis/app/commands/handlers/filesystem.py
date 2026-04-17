from __future__ import annotations

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


class CreateFolderHandler(CommandHandler):
    intents = ("create_folder",)
    description = "Create folders in common user locations."
    examples = (
        "Jarvis, create a folder on desktop called Projects",
        "Jarvis, make a folder in downloads named Receipts",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        name = str(request.slots["name"])
        location = str(request.slots["location"])
        target = context.system_service.create_folder(name, location, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Created folder '{name}' in {location}.",
            spoken_text=f"Created folder {name} in {location}.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target=name,
            launch_method="filesystem_create_folder",
            details=str(target),
        )


class CreateFileHandler(CommandHandler):
    intents = ("create_file",)
    description = "Create files in common user locations."
    examples = (
        "Jarvis, create a file on desktop called notes.txt",
        "Jarvis, make a file in documents named todo.md",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        name = str(request.slots["name"])
        location = str(request.slots["location"])
        target = context.system_service.create_file(name, location, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Created file '{name}' in {location}.",
            spoken_text=f"Created file {name} in {location}.",
            intent=request.intent,
            confidence=request.confidence,
            understood_target=name,
            launch_method="filesystem_create_file",
            details=str(target),
        )


class ScreenshotHandler(CommandHandler):
    intents = ("take_screenshot",)
    description = "Capture a screenshot."
    examples = ("Jarvis, take a screenshot",)

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        target = context.system_service.take_screenshot(context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Screenshot saved to {target}.",
            spoken_text="Screenshot captured.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="screenshot_capture",
            details=str(target),
        )
