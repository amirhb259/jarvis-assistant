from __future__ import annotations

import math

from PySide6.QtCore import Property, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class GlowOrb(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._pulse = 0.4
        self._state = "ready"
        self._speed = 0.06
        self._color = QColor("#39d2ff")

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.setMinimumSize(230, 230)

    def sizeHint(self) -> QSize:
        return QSize(260, 260)

    def _tick(self) -> None:
        self._phase += self._speed
        self._pulse = 0.52 + (math.sin(self._phase) * 0.16)
        self.update()

    def get_pulse(self) -> float:
        return self._pulse

    def set_pulse(self, value: float) -> None:
        self._pulse = value
        self.update()

    pulse = Property(float, get_pulse, set_pulse)

    def set_state(self, state: str) -> None:
        palette = {
            "ready": (QColor("#39d2ff"), 0.06),
            "listening": (QColor("#6bffdb"), 0.11),
            "thinking": (QColor("#58a6ff"), 0.17),
            "speaking": (QColor("#7dd3fc"), 0.09),
            "error": (QColor("#ff6b8f"), 0.08),
        }
        color, speed = palette.get(state, palette["ready"])
        self._state = state
        self._color = color
        self._speed = speed
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        size = min(self.width(), self.height())
        radius = size * 0.28
        center_x = self.width() / 2
        center_y = self.height() / 2

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        glow_radius = radius * (1.85 + self._pulse)
        glow = QRadialGradient(center_x, center_y, glow_radius)
        glow.setColorAt(0.0, self._color.lighter(140))
        outer = QColor(self._color)
        outer.setAlpha(18)
        glow.setColorAt(1.0, outer)
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(
            int(center_x - glow_radius),
            int(center_y - glow_radius),
            int(glow_radius * 2),
            int(glow_radius * 2),
        )

        for index, scale in enumerate((1.28, 1.54, 1.82), start=1):
            ring_color = QColor(self._color)
            ring_color.setAlpha(max(20, 80 - (index * 15)))
            painter.setPen(QPen(ring_color, 2.0))
            painter.setBrush(Qt.NoBrush)
            factor = scale + (math.sin(self._phase + index) * 0.04)
            ring_radius = radius * factor
            painter.drawEllipse(
                int(center_x - ring_radius),
                int(center_y - ring_radius),
                int(ring_radius * 2),
                int(ring_radius * 2),
            )

        orb = QRadialGradient(center_x - (radius * 0.18), center_y - (radius * 0.18), radius * 1.4)
        edge = QColor(self._color)
        edge.setAlpha(210)
        orb.setColorAt(0.0, QColor("#dff8ff"))
        orb.setColorAt(0.15, self._color.lighter(150))
        orb.setColorAt(0.58, QColor("#12354a"))
        orb.setColorAt(1.0, QColor("#09131d"))
        painter.setBrush(orb)
        painter.setPen(QPen(edge, 2.0))
        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2),
        )
