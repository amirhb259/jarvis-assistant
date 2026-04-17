from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from app.core.models import AppConfig, CommandRequest, CommandResult
from app.services.app_discovery_service import AppDiscoveryService
from app.services.app_launcher_service import AppLauncherService
from app.services.system_service import SystemService


EventSink = Callable[[str], None]


@dataclass
class ActionContext:
    config: AppConfig
    logger: logging.Logger
    system_service: SystemService
    app_discovery: AppDiscoveryService
    app_launcher: AppLauncherService
    emit_event: EventSink


class CommandHandler(ABC):
    intents: tuple[str, ...] = ()
    description: str = ""
    examples: tuple[str, ...] = ()
    dangerous: bool = False

    def confirmation_title(self, _request: CommandRequest) -> str:
        return "Confirm Action"

    def confirmation_message(self, _request: CommandRequest) -> str:
        return "Do you want Jarvis to continue?"

    @abstractmethod
    def handle(self, request: CommandRequest, context: ActionContext) -> CommandResult:
        raise NotImplementedError
