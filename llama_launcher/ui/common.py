"""通用 UI 构件。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


def make_button(text: str, variant: str = "", parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    if variant:
        button.setProperty("variant", variant)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return button


def card(title: str = "", subtitle: str = "", badge: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 15, 18, 15)
    layout.setSpacing(11)
    if title:
        header = QHBoxLayout()
        header.setSpacing(9)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        header.addWidget(label)
        if badge:
            chip = QLabel(badge)
            chip.setObjectName("Badge")
            header.addWidget(chip)
        header.addStretch(1)
        if subtitle:
            note = QLabel(subtitle)
            note.setObjectName("Muted")
            note.setWordWrap(True)
            note.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(note)
        layout.addLayout(header)
    return frame, layout


def field_row(label: str, widget: QWidget, width: int = 88) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(9)
    caption = QLabel(label)
    caption.setMinimumWidth(width)
    caption.setObjectName("EnvValue")
    row.addWidget(caption)
    row.addWidget(widget, 1)
    return row


def env_row(key: str, value: str, tooltip: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    left = QLabel(key)
    left.setObjectName("EnvKey")
    right = QLabel(value)
    right.setObjectName("EnvValue")
    right.setWordWrap(True)
    # 忽略自身宽度提示，避免长路径把整个侧栏的 sizeHint 撑大
    right.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    right.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if tooltip:
        right.setToolTip(tooltip)
    row.addWidget(left)
    row.addWidget(right, 1)
    return row


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line
