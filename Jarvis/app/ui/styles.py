APP_STYLESHEET = """
QMainWindow, QWidget#rootContainer {
    background-color: #061018;
    color: #e7f7ff;
    font-family: "Segoe UI";
    font-size: 13px;
}

QWidget {
    color: #e7f7ff;
}

QFrame#glassPanel {
    background-color: rgba(9, 20, 32, 230);
    border: 1px solid rgba(73, 184, 255, 70);
    border-radius: 24px;
}

QFrame#glassPanel[variant="secondary"] {
    background-color: rgba(11, 24, 38, 242);
}

QLabel#titleLabel {
    font-size: 30px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#subtitleLabel {
    color: #86bcd6;
    font-size: 13px;
}

QLabel#statusBadge {
    padding: 7px 14px;
    border-radius: 15px;
    background-color: rgba(35, 190, 255, 40);
    border: 1px solid rgba(80, 206, 255, 80);
    font-weight: 600;
}

QLabel#clockLabel {
    font-size: 22px;
    font-weight: 700;
    color: #9be9ff;
}

QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 700;
    color: #d4f6ff;
}

QLabel#orbStateLabel {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #aef2ff;
}

QLabel#orbHintLabel,
QLabel#sideHint,
QLabel#dialogBody,
QLabel#dialogCountdown {
    color: #83aeca;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 6px 0 6px 0;
}

QScrollBar::handle:vertical {
    border-radius: 5px;
    background: rgba(74, 169, 222, 120);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
}

QLineEdit, QPlainTextEdit, QListWidget, QTabWidget::pane, QSpinBox, QComboBox {
    background-color: rgba(5, 15, 25, 220);
    border: 1px solid rgba(77, 177, 230, 55);
    border-radius: 16px;
    padding: 10px 12px;
}

QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid rgba(78, 204, 255, 130);
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background-color: rgba(8, 18, 30, 245);
    border: 1px solid rgba(77, 177, 230, 55);
    selection-background-color: rgba(31, 95, 138, 180);
    padding: 6px;
}

QPushButton {
    border-radius: 16px;
    padding: 11px 16px;
    background-color: rgba(12, 31, 47, 245);
    border: 1px solid rgba(80, 190, 255, 70);
    color: #ebfbff;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(20, 44, 63, 250);
    border: 1px solid rgba(106, 216, 255, 120);
}

QPushButton#primaryButton,
QPushButton#sendButton {
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #0d7fb6,
        stop: 1 #1ed7ff
    );
    color: #051018;
    border: none;
}

QPushButton#micButton[active="true"] {
    background-color: rgba(58, 255, 214, 70);
    border: 1px solid rgba(129, 255, 232, 130);
}

QPushButton#dangerButton {
    background-color: rgba(80, 20, 28, 245);
    border: 1px solid rgba(255, 119, 140, 110);
}

QPushButton#dangerButton:hover {
    background-color: rgba(104, 25, 37, 250);
    border: 1px solid rgba(255, 146, 164, 130);
}

QTabBar::tab {
    background: transparent;
    color: #8fbad4;
    padding: 9px 16px;
    margin-right: 6px;
    border-radius: 12px;
}

QTabBar::tab:selected {
    color: #f0fbff;
    background-color: rgba(31, 95, 138, 150);
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 1px solid rgba(99, 184, 221, 90);
    background-color: rgba(8, 19, 31, 240);
}

QCheckBox::indicator:checked {
    background-color: #2fd5ff;
}

QLabel#bubbleTitle {
    color: #89bfd8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#bubbleBody {
    color: #effbff;
    font-size: 14px;
}

QLabel#bubbleTime {
    color: #6f9ab3;
    font-size: 11px;
}

QFrame[bubbleRole="assistant"] {
    background-color: rgba(13, 34, 53, 235);
    border: 1px solid rgba(69, 185, 255, 80);
    border-radius: 22px;
}

QFrame[bubbleRole="user"] {
    background-color: rgba(15, 47, 64, 235);
    border: 1px solid rgba(77, 225, 255, 90);
    border-radius: 22px;
}

QLabel#dialogTitle {
    font-size: 18px;
    font-weight: 700;
    color: #effbff;
}

QDialog#settingsOverlay {
    background-color: rgba(2, 9, 16, 170);
}

QFrame#overlayShell {
    background-color: rgba(7, 18, 29, 248);
    border: 1px solid rgba(84, 198, 255, 90);
    border-radius: 28px;
}

QLabel#overlayTitle {
    font-size: 24px;
    font-weight: 700;
    color: #effbff;
}

QLabel#overlaySubtitle {
    color: #83aeca;
    font-size: 13px;
}
"""
