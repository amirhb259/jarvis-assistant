from __future__ import annotations

from app.commands.base import CommandHandler


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, handler: CommandHandler) -> None:
        for intent in handler.intents:
            self._handlers[intent] = handler

    def get(self, intent: str) -> CommandHandler | None:
        return self._handlers.get(intent)

    def handlers(self) -> list[CommandHandler]:
        return list(dict.fromkeys(self._handlers.values()))

    def examples(self, limit: int = 8) -> list[str]:
        samples: list[str] = []
        for handler in self.handlers():
            samples.extend(handler.examples)
        return samples[:limit]
