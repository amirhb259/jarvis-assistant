from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AppConfig


class SettingsOverlay(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Jarvis Settings")
        self.setObjectName("settingsOverlay")
        self.resize(760, 780)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        shell = QFrame()
        shell.setObjectName("overlayShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(24, 24, 24, 24)
        shell_layout.setSpacing(18)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("overlayTitle")
        subtitle = QLabel("Voice, safety, indexing and desktop control")
        subtitle.setObjectName("overlaySubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        shell_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(16)

        self.general_card, self.general_form = self._form_card("General")
        self.voice_card, self.voice_form = self._form_card("Voice")
        self.safety_card, self.safety_form = self._form_card("Safety")
        self.index_card, self.index_form = self._form_card("App Index")

        self.body_layout.addWidget(self.general_card)
        self.body_layout.addWidget(self.voice_card)
        self.body_layout.addWidget(self.safety_card)
        self.body_layout.addWidget(self.index_card)
        self.body_layout.addStretch(1)

        scroll.setWidget(body)
        shell_layout.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        self.refresh_app_index_button = QPushButton("Refresh App Index")
        self.save_button = QPushButton("Save Settings")
        self.save_button.setObjectName("primaryButton")
        footer.addWidget(self.refresh_app_index_button)
        footer.addStretch(1)
        footer.addWidget(self.save_button)
        shell_layout.addLayout(footer)

        root.addWidget(shell)

        self.voice_input_checkbox = QCheckBox("Enable microphone input")
        self.voice_output_checkbox = QCheckBox("Enable spoken responses")
        self.dangerous_actions_checkbox = QCheckBox("Enable shutdown and restart actions")
        self.wake_word_checkbox = QCheckBox("Enable wake word architecture flag")
        self.startup_index_checkbox = QCheckBox("Refresh app index at startup when cache is empty")

        self.vosk_path_edit = QLineEdit()
        self.vosk_path_edit.setPlaceholderText(r"C:\models\vosk-model-small-en-us-0.15")
        self.mic_selector = QComboBox()
        self.mic_selector.setObjectName("settingsCombo")
        self.mic_selector.addItem("Default microphone", "")
        self.voice_hint_label = QLabel(
            "For German and English voice input, use a bilingual or multilingual Vosk model."
        )
        self.voice_hint_label.setObjectName("sideHint")
        self.voice_hint_label.setWordWrap(True)
        self.screenshot_dir_edit = QLineEdit()

        self.typing_delay_spin = QSpinBox()
        self.typing_delay_spin.setRange(0, 10)
        self.system_delay_spin = QSpinBox()
        self.system_delay_spin.setRange(0, 120)
        self.confirmation_timeout_spin = QSpinBox()
        self.confirmation_timeout_spin.setRange(5, 60)
        self.mouse_distance_spin = QSpinBox()
        self.mouse_distance_spin.setRange(50, 1000)
        self.clipboard_length_spin = QSpinBox()
        self.clipboard_length_spin.setRange(50, 5000)

        self.app_index_count_label = QLabel("0")
        self.app_index_updated_label = QLabel("Never")
        self.app_index_sources_label = QLabel("--")
        for label in (self.app_index_count_label, self.app_index_updated_label, self.app_index_sources_label):
            label.setObjectName("sideHint")
            label.setWordWrap(True)

        self.general_form.addRow(self.voice_input_checkbox)
        self.general_form.addRow(self.voice_output_checkbox)
        self.general_form.addRow(self.wake_word_checkbox)
        self.general_form.addRow(self.startup_index_checkbox)

        self.voice_form.addRow("Vosk model path", self.vosk_path_edit)
        self.voice_form.addRow("Microphone", self.mic_selector)
        self.voice_form.addRow(self.voice_hint_label)

        self.safety_form.addRow(self.dangerous_actions_checkbox)
        self.safety_form.addRow("Screenshot folder", self.screenshot_dir_edit)
        self.safety_form.addRow("Typing delay (s)", self.typing_delay_spin)
        self.safety_form.addRow("Shutdown/restart delay (s)", self.system_delay_spin)
        self.safety_form.addRow("Confirmation timeout (s)", self.confirmation_timeout_spin)
        self.safety_form.addRow("Mouse max distance", self.mouse_distance_spin)
        self.safety_form.addRow("Clipboard max length", self.clipboard_length_spin)

        self.index_form.addRow("Indexed apps", self.app_index_count_label)
        self.index_form.addRow("Last index update", self.app_index_updated_label)
        self.index_form.addRow("Sources", self.app_index_sources_label)

    def populate(self, config: AppConfig, devices: list[dict[str, object]], summary: dict[str, object]) -> None:
        self.voice_input_checkbox.setChecked(config.voice_input_enabled)
        self.voice_output_checkbox.setChecked(config.voice_output_enabled)
        self.dangerous_actions_checkbox.setChecked(config.dangerous_system_actions_enabled)
        self.wake_word_checkbox.setChecked(config.wake_word_enabled)
        self.startup_index_checkbox.setChecked(config.app_index_refresh_on_startup)
        self.vosk_path_edit.setText(config.vosk_model_path)
        self.screenshot_dir_edit.setText(config.screenshot_directory)
        self.typing_delay_spin.setValue(config.typing_delay_seconds)
        self.system_delay_spin.setValue(config.system_action_delay_seconds)
        self.confirmation_timeout_spin.setValue(config.confirmation_timeout_seconds)
        self.mouse_distance_spin.setValue(config.mouse_max_distance)
        self.clipboard_length_spin.setValue(config.clipboard_max_length)

        current_device = config.voice_input_device
        self.mic_selector.blockSignals(True)
        self.mic_selector.clear()
        self.mic_selector.addItem("Default microphone", "")
        selected_index = 0
        for idx, device in enumerate(devices, start=1):
            label = str(device["name"])
            self.mic_selector.addItem(label, label)
            if label == current_device:
                selected_index = idx
        self.mic_selector.setCurrentIndex(selected_index)
        self.mic_selector.blockSignals(False)

        self.app_index_count_label.setText(str(summary.get("count", 0)))
        self.app_index_updated_label.setText(str(summary.get("indexed_at", "Never")))
        sources = summary.get("sources", [])
        self.app_index_sources_label.setText(", ".join(sources) if sources else "--")

    def values(self) -> dict[str, object]:
        screenshot_dir = self.screenshot_dir_edit.text().strip()
        return {
            "voice_input_enabled": self.voice_input_checkbox.isChecked(),
            "voice_output_enabled": self.voice_output_checkbox.isChecked(),
            "dangerous_system_actions_enabled": self.dangerous_actions_checkbox.isChecked(),
            "wake_word_enabled": self.wake_word_checkbox.isChecked(),
            "app_index_refresh_on_startup": self.startup_index_checkbox.isChecked(),
            "vosk_model_path": self.vosk_path_edit.text().strip(),
            "voice_input_device": str(self.mic_selector.currentData() or ""),
            "screenshot_directory": screenshot_dir,
            "typing_delay_seconds": self.typing_delay_spin.value(),
            "system_action_delay_seconds": self.system_delay_spin.value(),
            "confirmation_timeout_seconds": self.confirmation_timeout_spin.value(),
            "mouse_max_distance": self.mouse_distance_spin.value(),
            "clipboard_max_length": self.clipboard_length_spin.value(),
        }

    @staticmethod
    def _form_card(title_text: str) -> tuple[QFrame, QFormLayout]:
        card = QFrame()
        card.setObjectName("glassPanel")
        card.setProperty("variant", "secondary")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)
        layout.addLayout(form)
        return card, form
