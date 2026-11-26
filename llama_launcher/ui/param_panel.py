"""根据参数 schema 自动生成的可编辑参数面板（支持搜索与启用态过滤）。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea, QSizePolicy, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..params import GROUPS, SPECS, ParamSpec, default_values, normalize_values
from .common import make_button


class ParamRow(QWidget):
    changed = Signal()

    def __init__(self, spec: ParamSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("ParamRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 5, 10, 5)
        layout.setSpacing(10)

        self.toggle = QCheckBox()
        self.toggle.setToolTip("勾选后该参数才会加入启动命令")
        layout.addWidget(self.toggle)

        caption = QVBoxLayout()
        caption.setSpacing(0)
        label = QLabel(spec.label)
        label.setObjectName("ParamLabel")
        label.setMinimumWidth(155)
        tooltip = spec.tip + (f"\n命令行：{spec.flag}" if spec.flag else "")
        label.setToolTip(tooltip.strip())
        caption.addWidget(label)
        flag = QLabel(spec.flag)
        flag.setObjectName("ParamFlag")
        flag.setToolTip(label.toolTip())
        caption.addWidget(flag)
        layout.addLayout(caption)

        self.input = self._build_input(spec)
        layout.addWidget(self.input, 1)

        if spec.kind == "path":
            browse = make_button("浏览", "flat", self)
            browse.setFixedWidth(58)
            browse.clicked.connect(self._browse)
            layout.addWidget(browse)

        if spec.kind == "flag":
            self.toggle.hide()

        self._connect()
        self._sync_active()

    def _build_input(self, spec: ParamSpec) -> QWidget:
        if spec.kind == "flag":
            widget = QCheckBox()
            widget.setChecked(bool(spec.default))
            return widget
        expanding = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if spec.kind == "int":
            widget = QSpinBox()
            widget.setRange(int(spec.minimum if spec.minimum is not None else 0),
                            int(spec.maximum if spec.maximum is not None else 100000))
            widget.setValue(int(spec.default or 0))
            widget.setMinimumWidth(135)
            widget.setSizePolicy(expanding)
            return widget
        if spec.kind == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            widget.setRange(float(spec.minimum if spec.minimum is not None else 0),
                            float(spec.maximum if spec.maximum is not None else 1e9))
            widget.setValue(float(spec.default or 0))
            widget.setSingleStep(0.05)
            widget.setMinimumWidth(135)
            widget.setSizePolicy(expanding)
            return widget
        if spec.kind == "choice":
            widget = QComboBox()
            for choice in spec.choices:
                widget.addItem(choice if choice else "未设置（不传参）", choice)
            index = widget.findData(spec.default)
            if index >= 0:
                widget.setCurrentIndex(index)
            widget.setSizePolicy(expanding)
            return widget
        widget = QLineEdit()
        widget.setText(str(spec.default or ""))
        widget.setPlaceholderText(spec.placeholder or "可选")
        widget.setClearButtonEnabled(True)
        if spec.key == "api_key":
            widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.setToolTip(spec.tip)
        return widget

    def _connect(self) -> None:
        self.toggle.toggled.connect(self._on_toggled)
        if isinstance(self.input, QCheckBox):
            self.input.toggled.connect(lambda: self.changed.emit())
        elif isinstance(self.input, (QSpinBox, QDoubleSpinBox)):
            self.input.valueChanged.connect(lambda: self.changed.emit())
        elif isinstance(self.input, QComboBox):
            self.input.currentIndexChanged.connect(lambda: self.changed.emit())
        elif isinstance(self.input, QLineEdit):
            self.input.textChanged.connect(lambda: self.changed.emit())

    def _on_toggled(self) -> None:
        self._sync_active()
        self.changed.emit()

    def _sync_active(self) -> None:
        active = True if self.spec.kind == "flag" else self.toggle.isChecked()
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def _browse(self) -> None:
        assert isinstance(self.input, QLineEdit)
        if self.spec.key == "log_file":
            path, _ = QFileDialog.getSaveFileName(
                self, "选择日志文件", self.input.text(), "日志文件 (*.log *.txt);;所有文件 (*)"
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择文件", self.input.text(), "GGUF 模型 (*.gguf);;所有文件 (*)"
            )
        if path:
            self.input.setText(path)

    def value(self) -> tuple[bool, Any]:
        if self.spec.kind == "flag":
            return bool(self.input.isChecked()), True
        if isinstance(self.input, QSpinBox):
            return self.toggle.isChecked(), self.input.value()
        if isinstance(self.input, QDoubleSpinBox):
            return self.toggle.isChecked(), self.input.value()
        if isinstance(self.input, QComboBox):
            return self.toggle.isChecked(), self.input.currentData()
        return self.toggle.isChecked(), self.input.text()

    def set_value(self, enabled: bool, value: Any) -> None:
        self.blockSignals(True)
        self.input.blockSignals(True)
        self.toggle.blockSignals(True)
        try:
            if self.spec.kind == "flag":
                self.input.setChecked(bool(value))
            elif isinstance(self.input, QSpinBox):
                self.input.setValue(int(value if value is not None else 0))
                self.toggle.setChecked(bool(enabled))
            elif isinstance(self.input, QDoubleSpinBox):
                self.input.setValue(float(value if value is not None else 0))
                self.toggle.setChecked(bool(enabled))
            elif isinstance(self.input, QComboBox):
                index = self.input.findData(value)
                self.input.setCurrentIndex(max(index, 0))
                self.toggle.setChecked(bool(enabled))
            else:
                self.input.setText("" if value is None else str(value))
                self.toggle.setChecked(bool(enabled))
        except (TypeError, ValueError):
            pass
        finally:
            self.blockSignals(False)
            self.input.blockSignals(False)
            self.toggle.blockSignals(False)
        self._sync_active()

    def matches(self, query: str, only_enabled: bool) -> bool:
        if only_enabled and self.spec.kind != "flag" and not self.toggle.isChecked():
            return False
        if not query:
            return True
        haystack = " ".join((self.spec.key, self.spec.flag, self.spec.label, self.spec.tip)).lower()
        return query.lower() in haystack


class ParamPanel(QWidget):
    paramsChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: dict[str, ParamRow] = {}
        self._tab_pages: list[tuple[QScrollArea, list[ParamRow]]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索参数名、说明或命令行标志…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search, 1)
        self.only_enabled = QCheckBox("仅看已启用")
        self.only_enabled.toggled.connect(self._apply_filter)
        toolbar.addWidget(self.only_enabled)
        self.count_label = QLabel("")
        self.count_label.setObjectName("Faint")
        self.count_label.setMinimumWidth(76)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        for group_id, group_name in GROUPS:
            container = QWidget()
            container.setObjectName("ParamPage")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(12, 10, 12, 10)
            container_layout.setSpacing(1)
            group_rows: list[ParamRow] = []
            for spec in SPECS:
                if spec.group != group_id:
                    continue
                row = ParamRow(spec)
                row.changed.connect(self._on_row_changed)
                self.rows[spec.key] = row
                group_rows.append(row)
                container_layout.addWidget(row)
            container_layout.addStretch(1)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, group_name)
            self._tab_pages.append((scroll, group_rows))

        self._apply_filter()

    def _on_row_changed(self) -> None:
        self._apply_filter()
        self.paramsChanged.emit()

    def _apply_filter(self) -> None:
        query = self.search.text().strip()
        only_enabled = self.only_enabled.isChecked()
        visible_total = 0
        visible_per_tab: list[int] = []
        for _scroll, rows in self._tab_pages:
            count = 0
            for row in rows:
                visible = row.matches(query, only_enabled)
                row.setVisible(visible)
                count += int(visible)
            visible_per_tab.append(count)
            visible_total += count

        if query or only_enabled:
            if visible_per_tab[self.tabs.currentIndex()] == 0:
                for index, count in enumerate(visible_per_tab):
                    if count:
                        self.tabs.setCurrentIndex(index)
                        break
        self.count_label.setText(f"显示 {visible_total}/{len(self.rows)}")

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, row in self.rows.items():
            enabled, value = row.value()
            result[key] = value
            result[f"{key}__enabled"] = enabled
        return result

    def apply_values(self, values: dict[str, Any]) -> None:
        normalized = normalize_values(values)
        for key, row in self.rows.items():
            row.set_value(normalized.get(f"{key}__enabled", False), normalized.get(key))
        self._apply_filter()

    def reset(self) -> None:
        self.apply_values(default_values())

    def enabled_count(self) -> int:
        values = self.values()
        return sum(1 for spec in SPECS if values.get(f"{spec.key}__enabled"))
