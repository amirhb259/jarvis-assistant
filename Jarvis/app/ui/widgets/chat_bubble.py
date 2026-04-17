from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ChatBubble(QFrame):
    def __init__(self, role: str, text: str, timestamp: str, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("bubbleRole", role)
        self.setMaximumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        title = QLabel("JARVIS" if role == "assistant" else "YOU")
        title.setObjectName("bubbleTitle")

        body = QLabel(text)
        body.setObjectName("bubbleBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)

        footer = QLabel(timestamp)
        footer.setObjectName("bubbleTime")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(footer, alignment=Qt.AlignRight)
