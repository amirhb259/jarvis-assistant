from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.commands.router import CommandRouter
from app.core.config_manager import ConfigManager
from app.core.history_store import HistoryStore
from app.core.models import AppConfig, CommandRequest, CommandResult, HistoryEntry
from app.services.app_discovery_service import AppDiscoveryService
from app.services.app_launcher_service import AppLauncherService
from app.services.conversation_context_service import ConversationContextService
from app.services.speech_service import SpeechRecognitionService
from app.services.system_service import SystemService
from app.services.tts_service import TextToSpeechService
from app.ui.styles import APP_STYLESHEET
from app.ui.widgets.chat_bubble import ChatBubble
from app.ui.widgets.confirmation_dialog import ConfirmationDialog
from app.ui.widgets.glow_orb import GlowOrb
from app.ui.widgets.settings_overlay import SettingsOverlay


class CommandWorkerSignals(QObject):
    activity = Signal(str)
    finished = Signal(object)


class CommandWorker(QRunnable):
    def __init__(
        self,
        router: CommandRouter,
        tts_service: TextToSpeechService,
        text: str | None = None,
        request: CommandRequest | None = None,
        conversation_context: dict[str, object] | None = None,
        confirmed: bool = False,
        speak: bool = True,
    ) -> None:
        super().__init__()
        self.router = router
        self.tts_service = tts_service
        self.text = text
        self.request = request
        self.conversation_context = conversation_context or {}
        self.confirmed = confirmed
        self.speak = speak
        self.signals = CommandWorkerSignals()

    @Slot()
    def run(self) -> None:
        if self.request is not None:
            result = self.router.process_request(
                self.request,
                conversation_context=self.conversation_context,
                emit_event=self.signals.activity.emit,
                confirmed=self.confirmed,
            )
        else:
            result = self.router.process_text_with_context(
                self.text or "",
                context=self.conversation_context,
                emit_event=self.signals.activity.emit,
                confirmed=self.confirmed,
            )

        self.signals.finished.emit(result)
        if self.speak and not result.requires_confirmation:
            spoken = result.spoken_text or result.message
            try:
                self.tts_service.speak(spoken)
            except Exception:
                pass


class SpeechWorkerSignals(QObject):
    activity = Signal(str)
    finished = Signal(str)
    failed = Signal(str)


class SpeechWorker(QRunnable):
    def __init__(self, speech_service: SpeechRecognitionService) -> None:
        super().__init__()
        self.speech_service = speech_service
        self.signals = SpeechWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            device_name = self.speech_service.config.voice_input_device or "default microphone"
            self.signals.activity.emit(f"Listening on {device_name}")
            text = self.speech_service.listen_once()
            self.signals.finished.emit(text)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class AppIndexWorkerSignals(QObject):
    activity = Signal(str)
    finished = Signal(object)
    failed = Signal(str)


class AppIndexWorker(QRunnable):
    def __init__(self, app_discovery: AppDiscoveryService) -> None:
        super().__init__()
        self.app_discovery = app_discovery
        self.signals = AppIndexWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            summary = self.app_discovery.refresh_index(self.signals.activity.emit)
            self.signals.finished.emit(summary)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_manager: ConfigManager,
        history_store: HistoryStore,
        router: CommandRouter,
        system_service: SystemService,
        app_discovery: AppDiscoveryService,
        app_launcher: AppLauncherService,
        conversation_context: ConversationContextService,
        speech_service: SpeechRecognitionService,
        tts_service: TextToSpeechService,
        logger,
    ) -> None:
        super().__init__()
        self.config_manager = config_manager
        self.history_store = history_store
        self.router = router
        self.system_service = system_service
        self.app_discovery = app_discovery
        self.app_launcher = app_launcher
        self.conversation_context = conversation_context
        self.speech_service = speech_service
        self.tts_service = tts_service
        self.logger = logger
        self.config = config_manager.config
        self.thread_pool = QThreadPool.globalInstance()
        self._tray_message_shown = False
        self._listening = False
        self.settings_overlay = SettingsOverlay(self)

        self.setWindowTitle(self.config.assistant_name)
        self.resize(1500, 920)
        self.setMinimumSize(1260, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_ui()
        self._load_history()
        self._wire_settings_overlay()
        self._create_tray_icon()
        self._refresh_settings_overlay()
        self._set_state("ready", "Standing by for commands")
        self._append_assistant_message(
            "Jarvis online. Try 'open Google', 'und such dort nach Lofi', 'focus Discord', 'copy that to clipboard', or 'take a screenshot'."
        )

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()

        self.voice_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.voice_shortcut.activated.connect(self._start_voice_capture)
        if self.config.app_index_refresh_on_startup and self.app_discovery.get_summary().get("count", 0) == 0:
            self._start_app_index_refresh(startup=True)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("rootContainer")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        layout.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_chat_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([320, 760, 360])
        layout.addWidget(splitter, stretch=1)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("glassPanel")
        row = QHBoxLayout(frame)
        row.setContentsMargins(24, 20, 24, 20)

        title_column = QVBoxLayout()
        title_column.setSpacing(4)

        title = QLabel(self.config.assistant_name.upper())
        title.setObjectName("titleLabel")

        subtitle = QLabel("Windows desktop automation cockpit")
        subtitle.setObjectName("subtitleLabel")

        self.status_badge = QLabel("READY")
        self.status_badge.setObjectName("statusBadge")

        self.clock_label = QLabel("--:--:--")
        self.clock_label.setObjectName("clockLabel")

        title_column.addWidget(title)
        title_column.addWidget(subtitle)

        row.addLayout(title_column)
        row.addStretch(1)
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._open_settings_overlay)
        row.addWidget(self.settings_button)
        row.addSpacing(10)
        row.addWidget(self.status_badge)
        row.addSpacing(12)
        row.addWidget(self.clock_label)
        return frame

    def _build_left_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("glassPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        self.orb = GlowOrb()
        self.orb_label = QLabel("READY")
        self.orb_label.setObjectName("orbStateLabel")
        self.orb_hint = QLabel("Text commands, microphone input, and guarded system controls.")
        self.orb_hint.setObjectName("orbHintLabel")
        self.orb_hint.setWordWrap(True)

        top = QVBoxLayout()
        top.setSpacing(10)
        top.setAlignment(Qt.AlignCenter)
        top.addWidget(self.orb, alignment=Qt.AlignCenter)
        top.addWidget(self.orb_label, alignment=Qt.AlignCenter)
        top.addWidget(self.orb_hint, alignment=Qt.AlignCenter)
        layout.addLayout(top)

        info_card = QFrame()
        info_card.setObjectName("glassPanel")
        info_card.setProperty("variant", "secondary")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(18, 18, 18, 18)
        info_layout.setSpacing(10)

        info_title = QLabel("Core Modes")
        info_title.setObjectName("sectionTitle")
        info_layout.addWidget(info_title)

        for line in (
            "Ctrl+Space starts one-shot voice capture.",
            "Dangerous actions require a timed confirmation dialog.",
            "Wake word architecture exists in config and is disabled by default.",
        ):
            label = QLabel(line)
            label.setObjectName("sideHint")
            label.setWordWrap(True)
            info_layout.addWidget(label)

        layout.addWidget(info_card)
        layout.addStretch(1)
        return frame

    def _build_chat_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("glassPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        title = QLabel("Conversation")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.NoFrame)

        self.chat_host = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_host)
        self.chat_layout.setContentsMargins(6, 6, 6, 6)
        self.chat_layout.setSpacing(14)
        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(self.chat_host)
        layout.addWidget(self.chat_scroll, stretch=1)

        composer = QFrame()
        composer.setObjectName("glassPanel")
        composer.setProperty("variant", "secondary")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(14, 14, 14, 14)
        composer_layout.setSpacing(12)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Type a command for Jarvis...")
        self.input_edit.returnPressed.connect(self._submit_text_command)

        self.mic_button = QPushButton("Mic")
        self.mic_button.setObjectName("micButton")
        self.mic_button.clicked.connect(self._start_voice_capture)

        self.stop_mic_button = QPushButton("Stop")
        self.stop_mic_button.setObjectName("dangerButton")
        self.stop_mic_button.clicked.connect(self._stop_voice_capture)
        self.stop_mic_button.hide()

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self._submit_text_command)

        composer_layout.addWidget(self.input_edit, stretch=1)
        composer_layout.addWidget(self.mic_button)
        composer_layout.addWidget(self.stop_mic_button)
        composer_layout.addWidget(self.send_button)

        layout.addWidget(composer)
        return frame

    def _build_right_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("glassPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self._build_interpretation_panel())
        tabs = QTabWidget()
        layout.addWidget(tabs)

        self.history_list = QListWidget()
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.trace_log = QPlainTextEdit()
        self.trace_log.setReadOnly(True)
        self.memory_log = QPlainTextEdit()
        self.memory_log.setReadOnly(True)

        tabs.addTab(self.history_list, "History")
        tabs.addTab(self.activity_log, "Activity")
        tabs.addTab(self.trace_log, "Agent Trace")
        tabs.addTab(self.memory_log, "Memory")
        return frame

    def _build_interpretation_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("glassPanel")
        frame.setProperty("variant", "secondary")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Understood")
        title.setObjectName("sectionTitle")

        self.intent_value = QLabel("Intent: --")
        self.target_value = QLabel("Target: --")
        self.confidence_value = QLabel("Confidence: --")
        self.tool_value = QLabel("Tool: --")
        self.tools_value = QLabel("Tools: --")
        self.method_value = QLabel("Method: --")
        self.status_value = QLabel("Status: --")
        self.safety_value = QLabel("Safety: --")
        self.plan_value = QLabel("Plan: --")

        for label in (
            self.intent_value,
            self.target_value,
            self.confidence_value,
            self.tool_value,
            self.tools_value,
            self.method_value,
            self.status_value,
            self.safety_value,
            self.plan_value,
        ):
            label.setObjectName("sideHint")
            label.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.intent_value)
        layout.addWidget(self.target_value)
        layout.addWidget(self.confidence_value)
        layout.addWidget(self.tool_value)
        layout.addWidget(self.tools_value)
        layout.addWidget(self.method_value)
        layout.addWidget(self.status_value)
        layout.addWidget(self.safety_value)
        layout.addWidget(self.plan_value)
        return frame

    def _create_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("computer"), self)
        if self.tray_icon.icon().isNull():
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        show_action = QAction("Show Jarvis", self)
        show_action.triggered.connect(self._restore_from_tray)

        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        context_menu = QMenu(self)
        context_menu.addAction(show_action)
        context_menu.addSeparator()
        context_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(context_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _save_settings(self) -> None:
        values = self.settings_overlay.values()
        screenshot_dir = str(values["screenshot_directory"]).strip() or self.config.screenshot_directory
        values["screenshot_directory"] = screenshot_dir
        updated = self.config_manager.update(**values)
        self._refresh_config(updated)
        self._append_activity("Settings saved")
        self._append_assistant_message("Settings updated.")
        self._refresh_settings_overlay()
        self.settings_overlay.accept()

    def _refresh_config(self, config: AppConfig) -> None:
        self.config = config
        self.router.update_config(config)
        self.system_service.update_config(config)
        self.app_discovery.update_config(config)
        self.app_launcher.update_config(config)
        self.speech_service.update_config(config)
        self.tts_service.update_config(config)

    def _load_history(self) -> None:
        try:
            entries = self.history_store.load()
        except Exception:
            entries = []

        for entry in entries:
            self._append_history_item(entry)

    def _append_history_item(self, entry: HistoryEntry) -> None:
        stamp = entry.timestamp.split(" ")[-1]
        prefix = "Jarvis" if entry.role == "assistant" else "You"
        item = QListWidgetItem(f"[{stamp}] {prefix}: {entry.text}")
        if not entry.success:
            item.setForeground(Qt.red)
        self.history_list.addItem(item)
        self.history_list.scrollToBottom()

    def _record_history(self, role: str, text: str, intent: str = "", success: bool = True) -> None:
        entry = HistoryEntry(
            timestamp=self._timestamp(),
            role=role,
            text=text,
            intent=intent,
            success=success,
        )
        self.history_store.append(entry)
        self._append_history_item(entry)

    def _append_chat_message(self, role: str, text: str) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 6, 0)
        bubble = ChatBubble(role, text, self._timestamp(short=True))
        if role == "assistant":
            row.addWidget(bubble, alignment=Qt.AlignLeft)
            row.addStretch(1)
        else:
            row.addStretch(1)
            row.addWidget(bubble, alignment=Qt.AlignRight)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, row)
        QTimer.singleShot(20, self._scroll_chat_to_bottom)

    def _append_assistant_message(self, text: str, intent: str = "", success: bool = True) -> None:
        self._append_chat_message("assistant", text)
        self._record_history("assistant", text, intent=intent, success=success)

    def _append_user_message(self, text: str) -> None:
        self._append_chat_message("user", text)
        self._record_history("user", text)

    def _append_activity(self, text: str) -> None:
        stamp = self._timestamp(short=True)
        self.activity_log.appendPlainText(f"[{stamp}] {text}")
        self.activity_log.verticalScrollBar().setValue(self.activity_log.verticalScrollBar().maximum())
        self.logger.info(text)

    def _refresh_settings_overlay(self) -> None:
        summary = self.app_discovery.get_summary()
        self.settings_overlay.populate(self.config, self.speech_service.available_input_devices(), summary)

    def _start_app_index_refresh(self, startup: bool = False) -> None:
        self.settings_overlay.refresh_app_index_button.setDisabled(True)
        self._append_activity("Refreshing the installed app index")
        if not startup:
            self._append_assistant_message("Refreshing the installed app index. This can take a little while.")
        worker = AppIndexWorker(self.app_discovery)
        worker.signals.activity.connect(self._append_activity)
        worker.signals.finished.connect(self._handle_app_index_refresh_done)
        worker.signals.failed.connect(self._handle_app_index_refresh_failed)
        self.thread_pool.start(worker)

    def _handle_app_index_refresh_done(self, _summary: object) -> None:
        self.settings_overlay.refresh_app_index_button.setDisabled(False)
        self._refresh_settings_overlay()
        self._append_activity("App index refresh completed")
        self._append_assistant_message(
            f"App index refreshed. Jarvis can currently see about {self.app_discovery.get_summary().get('count', 0)} launchable apps."
        )

    def _handle_app_index_refresh_failed(self, error: str) -> None:
        self.settings_overlay.refresh_app_index_button.setDisabled(False)
        self._append_activity(f"App index refresh failed: {error}")
        self._append_assistant_message(f"App index refresh failed: {error}", success=False)

    def _update_understanding_panel(self, result: CommandResult) -> None:
        intent = result.intent or "--"
        target = result.understood_target or "--"
        confidence = f"{result.confidence:.2f}" if result.confidence else "--"
        tool = result.selected_tool or "--"
        tools = ", ".join(result.selected_tools) if result.selected_tools else "--"
        method = result.launch_method or "--"
        status = result.execution_status or "--"
        safety = ", ".join(result.safety_flags) if result.safety_flags else "--"
        plan = result.plan_summary or "--"
        self.intent_value.setText(f"Intent: {intent}")
        self.target_value.setText(f"Target: {target}")
        self.confidence_value.setText(f"Confidence: {confidence}")
        self.tool_value.setText(f"Tool: {tool}")
        self.tools_value.setText(f"Tools: {tools}")
        self.method_value.setText(f"Method: {method}")
        self.status_value.setText(f"Status: {status}")
        self.safety_value.setText(f"Safety: {safety}")
        self.plan_value.setText(f"Plan: {plan}")

    def _submit_text_command(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self._append_user_message(text)
        self.conversation_context.record_user_turn(text)
        self._execute_text_command(text)

    def _execute_text_command(self, text: str) -> None:
        self._set_busy(True)
        self._set_state("thinking", "Parsing and executing command")
        worker = CommandWorker(
            self.router,
            self.tts_service,
            text=text,
            conversation_context=self.conversation_context.snapshot(),
            speak=self.config.voice_output_enabled,
        )
        worker.signals.activity.connect(self._append_activity)
        worker.signals.finished.connect(self._handle_command_result)
        self.thread_pool.start(worker)

    def _execute_request(self, request: CommandRequest, confirmed: bool) -> None:
        self._set_busy(True)
        self._set_state("thinking", "Executing confirmed action")
        worker = CommandWorker(
            self.router,
            self.tts_service,
            request=request,
            conversation_context=self.conversation_context.snapshot(),
            confirmed=confirmed,
            speak=self.config.voice_output_enabled,
        )
        worker.signals.activity.connect(self._append_activity)
        worker.signals.finished.connect(self._handle_command_result)
        self.thread_pool.start(worker)

    def _handle_command_result(self, result: CommandResult) -> None:
        self._set_busy(False)
        self._update_understanding_panel(result)
        self.trace_log.setPlainText(json.dumps(result.agent_trace or {}, indent=2, ensure_ascii=False))
        self.memory_log.setPlainText(json.dumps(self.conversation_context.snapshot(), indent=2, ensure_ascii=False))
        if result.extracted_entities:
            entity_summary = ", ".join(
                f"{item.get('kind', 'entity')}={item.get('value', '')}" for item in result.extracted_entities
            )
            self._append_activity(f"Entities: {entity_summary}")
        if result.selected_tools:
            self._append_activity(f"Selected tools: {', '.join(result.selected_tools)}")
        if result.safety_flags:
            self._append_activity(f"Safety flags: {', '.join(result.safety_flags)}")
        self._append_activity(
            f"Result intent={result.intent} confidence={result.confidence:.2f} tool={result.selected_tool or '-'} status={result.execution_status}"
        )
        if result.requires_confirmation and result.pending_request:
            self._set_state("ready", "Awaiting confirmation")
            self._append_assistant_message(result.confirmation_message, intent=result.intent, success=False)
            dialog = ConfirmationDialog(
                result.confirmation_title,
                result.confirmation_message,
                self.config.confirmation_timeout_seconds,
                self,
            )
            if dialog.exec() == dialog.Accepted:
                self._append_activity("Sensitive action confirmed by user")
                self._execute_request(result.pending_request, confirmed=True)
            else:
                self._append_activity("Sensitive action canceled")
                self._append_assistant_message("Canceled that action.", intent=result.intent, success=True)
            return

        message = result.message
        if result.details:
            message = f"{message}\n{result.details}"
        if result.suggestions:
            message = f"{message}\nSuggestions: {', '.join(result.suggestions)}"
        if result.plan_summary:
            message = f"{message}\nPlan: {result.plan_summary}"

        self._append_assistant_message(message, intent=result.intent, success=result.ok)
        if result.ok:
            self._set_state("speaking", "Response ready")
            QTimer.singleShot(1300, lambda: self._set_state("ready", "Standing by for commands"))
        else:
            self._set_state("error", "Command failed")
            QTimer.singleShot(1800, lambda: self._set_state("ready", "Standing by for commands"))

    def _start_voice_capture(self) -> None:
        if not self.config.voice_input_enabled:
            self._append_assistant_message("Voice input is disabled in settings.")
            return
        if self._listening:
            return

        self._listening = True
        self._set_busy(True)
        self._set_state("listening", "Listening for a voice command. Press Stop when you are done.")
        self.mic_button.setProperty("active", True)
        self.style().polish(self.mic_button)
        self.stop_mic_button.show()
        self.stop_mic_button.setDisabled(False)

        worker = SpeechWorker(self.speech_service)
        worker.signals.activity.connect(self._append_activity)
        worker.signals.finished.connect(self._handle_voice_text)
        worker.signals.failed.connect(self._handle_voice_error)
        self.thread_pool.start(worker)

    def _stop_voice_capture(self) -> None:
        if not self._listening:
            return
        self._append_activity("Stopping voice capture")
        self.stop_mic_button.setDisabled(True)
        self.speech_service.stop_listening()

    def _handle_voice_text(self, text: str) -> None:
        self._reset_voice_capture_ui()
        self._append_activity(f"Recognized speech: {text}")
        self._append_user_message(text)
        self.conversation_context.record_user_turn(text)
        self._execute_text_command(text)

    def _handle_voice_error(self, error: str) -> None:
        self._reset_voice_capture_ui()
        if error == "Voice capture stopped.":
            self._set_state("ready", "Voice capture stopped")
            self._append_assistant_message("Voice capture stopped.", success=True)
            QTimer.singleShot(1000, lambda: self._set_state("ready", "Standing by for commands"))
            return
        self._set_state("error", "Voice capture failed")
        self._append_assistant_message(f"Voice input failed: {error}", success=False)
        QTimer.singleShot(1500, lambda: self._set_state("ready", "Standing by for commands"))

    def _set_state(self, state: str, subtitle: str) -> None:
        labels = {
            "ready": "READY",
            "thinking": "THINKING",
            "listening": "LISTENING",
            "speaking": "RESPONDING",
            "error": "ERROR",
        }
        label = labels.get(state, state.upper())
        self.orb.set_state(state)
        self.orb_label.setText(label)
        self.orb_hint.setText(subtitle)
        self.status_badge.setText(label)

    def _set_busy(self, busy: bool) -> None:
        self.input_edit.setDisabled(busy)
        self.send_button.setDisabled(busy)
        self.mic_button.setDisabled(busy and not self._listening)

    def _scroll_chat_to_bottom(self) -> None:
        bar = self.chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _timestamp(self, short: bool = False) -> str:
        return datetime.now().strftime("%H:%M:%S" if short else "%Y-%m-%d %H:%M:%S")

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:  # noqa: ANN001
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    def _wire_settings_overlay(self) -> None:
        self.settings_overlay.save_button.clicked.connect(self._save_settings)
        self.settings_overlay.refresh_app_index_button.clicked.connect(self._start_app_index_refresh)

    def _open_settings_overlay(self) -> None:
        self._refresh_settings_overlay()
        self.settings_overlay.exec()

    def _reset_voice_capture_ui(self) -> None:
        self._listening = False
        self._set_busy(False)
        self.mic_button.setProperty("active", False)
        self.style().polish(self.mic_button)
        self.stop_mic_button.hide()
        self.stop_mic_button.setDisabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            if not self._tray_message_shown:
                self.tray_icon.showMessage(
                    "Jarvis",
                    "Jarvis is still running in the system tray. Use the tray menu to exit.",
                    QSystemTrayIcon.Information,
                    2500,
                )
                self._tray_message_shown = True
            return
        super().closeEvent(event)
