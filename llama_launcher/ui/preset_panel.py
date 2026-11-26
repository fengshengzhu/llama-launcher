"""左侧参数预设面板。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from .common import card, make_button

_ROLE = Qt.ItemDataRole.UserRole


def _dot_icon(color: str) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 10, 10)
    painter.end()
    return QIcon(pixmap)


class PresetPanel(QWidget):
    apply_requested = Signal(str)
    save_requested = Signal()
    overwrite_requested = Signal(str)
    delete_requested = Signal(str)
    import_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.presets: dict[str, dict[str, Any]] = {}
        self._builtin_icon = _dot_icon("#6d8dff")
        self._custom_icon = _dot_icon("#3fd39c")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)

        frame, inner = card("参数预设", "一键切换配置")
        layout.addWidget(frame, 1)

        self.list_widget = QListWidget()
        self.list_widget.setToolTip("双击预设即可应用")
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.list_widget.itemDoubleClicked.connect(lambda: self._emit_apply())
        inner.addWidget(self.list_widget, 1)

        self.badge = QLabel("内置预设")
        self.badge.setObjectName("Badge")
        badge_row = QHBoxLayout()
        badge_row.addWidget(self.badge)
        badge_row.addStretch(1)
        inner.addLayout(badge_row)

        self.description = QLabel("选择一个预设查看说明")
        self.description.setObjectName("Hint")
        self.description.setWordWrap(True)
        self.description.setMinimumHeight(46)
        inner.addWidget(self.description)

        apply_button = make_button("应用预设", "primary")
        apply_button.clicked.connect(self._emit_apply)
        inner.addWidget(apply_button)

        save_button = make_button("另存为新预设")
        save_button.clicked.connect(self.save_requested.emit)
        inner.addWidget(save_button)

        pair = QHBoxLayout()
        pair.setSpacing(8)
        overwrite = make_button("覆盖所选")
        overwrite.clicked.connect(self._emit_overwrite)
        delete = make_button("删除", "danger")
        delete.clicked.connect(self._emit_delete)
        pair.addWidget(overwrite)
        pair.addWidget(delete)
        inner.addLayout(pair)

        io = QHBoxLayout()
        io.setSpacing(8)
        import_button = make_button("导入")
        import_button.clicked.connect(self.import_requested.emit)
        export_button = make_button("导出")
        export_button.clicked.connect(self.export_requested.emit)
        io.addWidget(import_button)
        io.addWidget(export_button)
        inner.addLayout(io)

    def set_presets(self, presets: dict[str, dict[str, Any]], active_key: str = "") -> None:
        self.presets = presets
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        target_row = 0
        for row, (key, preset) in enumerate(presets.items()):
            builtin = bool(preset.get("builtin"))
            item = QListWidgetItem(self._builtin_icon if builtin else self._custom_icon,
                                   preset.get("name", key))
            item.setData(_ROLE, key)
            item.setToolTip(preset.get("description", ""))
            self.list_widget.addItem(item)
            if key == active_key:
                target_row = row
        self.list_widget.blockSignals(False)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(target_row)
        self._update_description()

    def selected_key(self) -> str:
        item = self.list_widget.currentItem()
        return item.data(_ROLE) if item else ""

    def _on_current_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._update_description()

    def _update_description(self) -> None:
        preset = self.presets.get(self.selected_key())
        if not preset:
            self.description.setText("选择一个预设查看说明")
            self.badge.setText("—")
            return
        builtin = bool(preset.get("builtin"))
        self.badge.setText("内置预设" if builtin else "自定义预设")
        self.badge.setObjectName("Badge" if builtin else "BadgeOk")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.description.setText(preset.get("description") or "暂无说明")

    def _emit_apply(self) -> None:
        key = self.selected_key()
        if key:
            self.apply_requested.emit(key)

    def _emit_overwrite(self) -> None:
        key = self.selected_key()
        if key:
            self.overwrite_requested.emit(key)

    def _emit_delete(self) -> None:
        key = self.selected_key()
        if key:
            self.delete_requested.emit(key)
