from __future__ import annotations

import logging
from typing import Callable

from app.commands.base import ActionContext
from app.commands.handlers.desktop import ClipboardReadHandler, ClipboardWriteHandler, FocusWindowHandler
from app.commands.handlers.applications import OpenApplicationHandler
from app.commands.handlers.filesystem import CreateFileHandler, CreateFolderHandler, ScreenshotHandler
from app.commands.handlers.info import DateTimeHandler
from app.commands.handlers.system import (
    CancelSystemActionHandler,
    LockHandler,
    MouseHandler,
    RestartHandler,
    ShutdownHandler,
    TypeTextHandler,
    VolumeHandler,
)
from app.commands.handlers.web import OpenWebsiteHandler, SearchHandler
from app.commands.registry import CommandRegistry
from app.core.agent_core import AgentCore
from app.core.guardrails import Guardrails
from app.core.models import AppConfig, CommandRequest, CommandResult
from app.core.tool_registry import ToolDefinition, ToolRegistry
from app.services.app_discovery_service import AppDiscoveryService
from app.services.app_launcher_service import AppLauncherService
from app.services.brain_service import JarvisBrainService
from app.services.conversation_context_service import ConversationContextService
from app.services.entity_extractor_service import EntityExtractorService
from app.services.nlu_service import NLUService
from app.services.system_service import SystemService


EventSink = Callable[[str], None]


class CommandRouter:
    def __init__(
        self,
        config: AppConfig,
        system_service: SystemService,
        app_discovery: AppDiscoveryService,
        app_launcher: AppLauncherService,
        conversation_context: ConversationContextService,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.system_service = system_service
        self.app_discovery = app_discovery
        self.app_launcher = app_launcher
        self.conversation_context = conversation_context
        self.logger = logger

        self.registry = self._build_registry()
        self.tool_registry = self._build_tool_registry(self.registry)
        self.nlu = NLUService(config, app_discovery)
        self.entity_extractor = EntityExtractorService(config)
        self.brain = JarvisBrainService(config, self.nlu, self.entity_extractor, self.registry, logger)
        self.guardrails = Guardrails(config)
        self.agent_core = AgentCore(
            config=config,
            brain=self.brain,
            command_registry=self.registry,
            tool_registry=self.tool_registry,
            context_memory=conversation_context,
            guardrails=self.guardrails,
            logger=logger,
        )

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        self.agent_core.update_config(config)

    def process_text(self, text: str, emit_event: EventSink | None = None, confirmed: bool = False) -> CommandResult:
        return self.process_text_with_context(text, context=None, emit_event=emit_event, confirmed=confirmed)

    def handle_user_command(
        self,
        user_text: str,
        context: dict[str, object] | None = None,
        emit_event: EventSink | None = None,
        confirmed: bool = False,
    ) -> CommandResult:
        return self.process_text_with_context(user_text, context=context, emit_event=emit_event, confirmed=confirmed)

    def process_text_with_context(
        self,
        text: str,
        context: dict[str, object] | None = None,
        emit_event: EventSink | None = None,
        confirmed: bool = False,
    ) -> CommandResult:
        return self.agent_core.handle_user_command(
            user_text=text,
            action_context=self._action_context(emit_event),
            context=context or self.conversation_context.snapshot(),
            emit_event=emit_event,
            confirmed=confirmed,
        )

    def process_request(
        self,
        request: CommandRequest,
        conversation_context: dict[str, object] | None = None,
        emit_event: EventSink | None = None,
        confirmed: bool = False,
    ) -> CommandResult:
        if request.plan is None:
            request = self.agent_core.detect_intent(
                request.raw_text,
                conversation_context or request.context_data or self.conversation_context.snapshot(),
                emit_event=emit_event,
            )
        return self.agent_core.execute_request(
            request=request,
            action_context=self._action_context(emit_event),
            context=conversation_context or request.context_data or self.conversation_context.snapshot(),
            emit_event=emit_event,
            confirmed=confirmed,
        )

    def _action_context(self, emit_event: EventSink | None) -> ActionContext:
        return ActionContext(
            config=self.config,
            logger=self.logger,
            system_service=self.system_service,
            app_discovery=self.app_discovery,
            app_launcher=self.app_launcher,
            emit_event=emit_event or (lambda _message: None),
        )

    @staticmethod
    def _build_registry() -> CommandRegistry:
        registry = CommandRegistry()
        for handler in (
            OpenWebsiteHandler(),
            SearchHandler(),
            OpenApplicationHandler(),
            FocusWindowHandler(),
            CreateFolderHandler(),
            CreateFileHandler(),
            ScreenshotHandler(),
            DateTimeHandler(),
            VolumeHandler(),
            ShutdownHandler(),
            RestartHandler(),
            LockHandler(),
            CancelSystemActionHandler(),
            TypeTextHandler(),
            MouseHandler(),
            ClipboardReadHandler(),
            ClipboardWriteHandler(),
        ):
            registry.register(handler)
        return registry

    @staticmethod
    def _build_tool_registry(registry: CommandRegistry) -> ToolRegistry:
        schemas = {
            "open_website": {"target": "str"},
            "search_google": {"query": "str"},
            "search_youtube": {"query": "str"},
            "open_app": {"target": "str"},
            "create_folder": {"location": "str", "name": "str"},
            "create_file": {"location": "str", "name": "str"},
            "take_screenshot": {},
            "tell_time": {},
            "tell_date": {},
            "volume_up": {"value": "int"},
            "volume_down": {"value": "int"},
            "set_volume": {"value": "int"},
            "mute_volume": {},
            "unmute_volume": {},
            "shutdown_pc": {},
            "restart_pc": {},
            "lock_pc": {},
            "cancel_system_action": {},
            "type_text": {"text": "str"},
            "move_mouse": {"direction": "str", "distance": "int"},
            "click_mouse": {"button": "str"},
            "focus_window": {"target": "str"},
            "clipboard_read": {},
            "clipboard_write": {"text": "str"},
        }
        specialists = {
            "open_website": "browser_agent",
            "search_google": "browser_agent",
            "search_youtube": "browser_agent",
            "open_app": "desktop_agent",
            "create_folder": "filesystem_agent",
            "create_file": "filesystem_agent",
            "take_screenshot": "desktop_agent",
            "tell_time": "system_control_agent",
            "tell_date": "system_control_agent",
            "volume_up": "system_control_agent",
            "volume_down": "system_control_agent",
            "set_volume": "system_control_agent",
            "mute_volume": "system_control_agent",
            "unmute_volume": "system_control_agent",
            "shutdown_pc": "system_control_agent",
            "restart_pc": "system_control_agent",
            "lock_pc": "system_control_agent",
            "cancel_system_action": "system_control_agent",
            "type_text": "desktop_agent",
            "move_mouse": "desktop_agent",
            "click_mouse": "desktop_agent",
            "focus_window": "desktop_agent",
            "clipboard_read": "desktop_agent",
            "clipboard_write": "desktop_agent",
        }
        registry_tools = ToolRegistry()
        for handler in registry.handlers():
            for intent in handler.intents:
                registry_tools.register_tool(
                    ToolDefinition(
                        name=intent,
                        description=handler.description,
                        input_schema=schemas.get(intent, {}),
                        executor=handler.handle,
                        dangerous=handler.dangerous,
                        specialist=specialists.get(intent, "general_agent"),
                        intents=(intent,),
                    )
                )
        return registry_tools
