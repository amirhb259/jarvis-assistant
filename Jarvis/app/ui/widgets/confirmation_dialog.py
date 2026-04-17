from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PySide6.QtCore import QTimer


class ConfirmationDialog(QDialog):
    def __init__(self, title: str, message: str, timeout_seconds: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._remaining = max(3, int(timeout_seconds))

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")

        body_label = QLabel(message)
        body_label.setObjectName("dialogBody")
        body_label.setWordWrap(True)

        self.countdown_label = QLabel()
        self.countdown_label.setObjectName("dialogCountdown")
        self._refresh_countdown()

        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        confirm_button = QPushButton("Confirm")
        confirm_button.setObjectName("primaryButton")
        confirm_button.clicked.connect(self.accept)

        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(confirm_button)

        root.addWidget(title_label)
        root.addWidget(body_label)
        root.addWidget(self.countdown_label)
        root.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._remaining -= 1
        self._refresh_countdown()
        if self._remaining <= 0:
            self.reject()

    def _refresh_countdown(self) -> None:
        self.countdown_label.setText(f"Auto-cancel in {self._remaining}s")
