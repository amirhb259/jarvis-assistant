from __future__ import annotations

from app.commands.base import ActionContext, CommandHandler
from app.core.models import CommandRequest, CommandResult


class VolumeHandler(CommandHandler):
    intents = ("volume_up", "volume_down", "set_volume", "mute_volume", "unmute_volume")
    description = "Control system volume."
    examples = (
        "Jarvis, volume up",
        "Jarvis, set volume to 40",
        "Jarvis, mute",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        if request.intent == "mute_volume":
            context.system_service.mute(context.emit_event)
            return CommandResult(
                ok=True,
                message="Muted the volume.",
                spoken_text="Volume muted.",
                intent=request.intent,
                confidence=request.confidence,
                launch_method="volume_mute",
            )

        if request.intent == "unmute_volume":
            context.system_service.unmute(context.emit_event)
            return CommandResult(
                ok=True,
                message="Unmuted the volume.",
                spoken_text="Volume unmuted.",
                intent=request.intent,
                confidence=request.confidence,
                launch_method="volume_unmute",
            )

        value = int(request.slots["value"])
        if request.intent == "set_volume":
            percent = context.system_service.set_volume(value, context.emit_event)
            return CommandResult(
                ok=True,
                message=f"Volume set to {percent}%.",
                spoken_text=f"Volume set to {percent} percent.",
                intent=request.intent,
                confidence=request.confidence,
                launch_method="volume_set",
            )

        delta = value if request.intent == "volume_up" else -value
        percent = context.system_service.change_volume(delta, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Volume adjusted to {percent}%.",
            spoken_text=f"Volume adjusted to {percent} percent.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="volume_adjust",
        )


class ShutdownHandler(CommandHandler):
    intents = ("shutdown_pc",)
    description = "Shut down the PC after confirmation."
    examples = ("Jarvis, shutdown the PC",)
    dangerous = True

    def confirmation_title(self, _request: CommandRequest) -> str:
        return "Shutdown Confirmation"

    def confirmation_message(self, context_request: CommandRequest) -> str:
        return (
            "Jarvis is about to shut down Windows.\n\n"
            "This will use the configured shutdown delay so you can still cancel it."
        )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        delay = context.system_service.schedule_shutdown(context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Shutdown scheduled in {delay} seconds. Say 'cancel shutdown' to stop it.",
            spoken_text=f"Shutdown scheduled in {delay} seconds.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="shutdown_schedule",
        )


class RestartHandler(CommandHandler):
    intents = ("restart_pc",)
    description = "Restart the PC after confirmation."
    examples = ("Jarvis, restart the PC",)
    dangerous = True

    def confirmation_title(self, _request: CommandRequest) -> str:
        return "Restart Confirmation"

    def confirmation_message(self, _request: CommandRequest) -> str:
        return (
            "Jarvis is about to restart Windows.\n\n"
            "This will use the configured restart delay so you can still cancel it."
        )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        delay = context.system_service.schedule_restart(context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Restart scheduled in {delay} seconds. Say 'cancel shutdown' to stop it.",
            spoken_text=f"Restart scheduled in {delay} seconds.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="restart_schedule",
        )


class LockHandler(CommandHandler):
    intents = ("lock_pc",)
    description = "Lock the workstation."
    examples = ("Jarvis, lock the PC",)

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        context.system_service.lock_pc(context.emit_event)
        return CommandResult(
            ok=True,
            message="Locking the PC.",
            spoken_text="Locking the PC.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="lock_pc",
        )


class CancelSystemActionHandler(CommandHandler):
    intents = ("cancel_system_action",)
    description = "Cancel a pending shutdown or restart."
    examples = ("Jarvis, cancel shutdown",)

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        context.system_service.cancel_pending_shutdown(context.emit_event)
        return CommandResult(
            ok=True,
            message="Canceled the pending shutdown or restart.",
            spoken_text="Canceled the pending shutdown or restart.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="cancel_system_action",
        )


class TypeTextHandler(CommandHandler):
    intents = ("type_text",)
    description = "Type text into the active window."
    examples = ('Jarvis, type text for me "Hello from Jarvis"',)

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        text = str(request.slots["text"])
        context.system_service.type_text(text, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Typed {len(text)} characters into the active window.",
            spoken_text="Finished typing.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="type_text",
        )


class MouseHandler(CommandHandler):
    intents = ("move_mouse", "click_mouse")
    description = "Move or click the mouse with safe limits."
    examples = (
        "Jarvis, move the mouse right 100",
        "Jarvis, left click",
    )

    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        if request.intent == "click_mouse":
            button = str(request.slots["button"])
            context.system_service.click_mouse(button, context.emit_event)
            return CommandResult(
                ok=True,
                message=f"Performed a {button} click.",
                spoken_text=f"{button.capitalize()} click complete.",
                intent=request.intent,
                confidence=request.confidence,
                launch_method="mouse_click",
            )

        direction = str(request.slots["direction"])
        distance = int(request.slots["distance"])
        x, y = context.system_service.move_mouse(direction, distance, context.emit_event)
        return CommandResult(
            ok=True,
            message=f"Moved the mouse {direction} to approximately ({x}, {y}).",
            spoken_text=f"Moved the mouse {direction}.",
            intent=request.intent,
            confidence=request.confidence,
            launch_method="mouse_move",
        )
