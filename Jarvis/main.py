from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.commands.router import CommandRouter
from app.core.config_manager import ConfigManager
from app.core.history_store import HistoryStore
from app.core.logger import setup_logger
from app.core.paths import ensure_runtime_dirs
from app.services.app_discovery_service import AppDiscoveryService
from app.services.app_launcher_service import AppLauncherService
from app.services.conversation_context_service import ConversationContextService
from app.services.speech_service import SpeechRecognitionService
from app.services.system_service import SystemService
from app.services.tts_service import TextToSpeechService
from app.ui.main_window import MainWindow


def main() -> int:
    ensure_runtime_dirs()
    config_manager = ConfigManager()
    logger = setup_logger(config_manager.config.log_file)
    history_store = HistoryStore(config_manager.config.history_file)

    system_service = SystemService(config_manager.config)
    app_discovery = AppDiscoveryService(config_manager.config, logger)
    app_launcher = AppLauncherService(config_manager.config, app_discovery, logger)
    conversation_context = ConversationContextService()
    speech_service = SpeechRecognitionService(config_manager.config)
    tts_service = TextToSpeechService(config_manager.config)
    router = CommandRouter(
        config_manager.config,
        system_service,
        app_discovery,
        app_launcher,
        conversation_context,
        logger,
    )

    app = QApplication(sys.argv)
    app.setApplicationName(config_manager.config.assistant_name)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow(
        config_manager=config_manager,
        history_store=history_store,
        router=router,
        system_service=system_service,
        app_discovery=app_discovery,
        app_launcher=app_launcher,
        conversation_context=conversation_context,
        speech_service=speech_service,
        tts_service=tts_service,
        logger=logger,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
