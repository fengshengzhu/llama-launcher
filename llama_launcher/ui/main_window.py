"""主窗口：应用栏、启动配置、参数预设、控制台、状态栏与主题。"""

from __future__ import annotations

import os
import platform
from datetime import datetime

from PySide6.QtCore import QByteArray, QElapsedTimer, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from .. import __version__
from ..config import ConfigManager
from ..params import SPECS, build_command, normalize_values, parse_extra_args, shell_join
from ..platform_utils import (
    find_binary, inspect_model, open_download_page, port_available, probe_version, server_name,
)
from ..runner import HealthChecker, ServerRunner, server_url
from ..theme import ThemeManager
from .common import card, env_row, field_row, make_button
from .param_panel import ParamPanel
from .preset_panel import PresetPanel

MAX_LOG_LINES = 3000


class MainWindow(QMainWindow):
    THEME_LABELS = {"system": "跟随系统", "light": "浅色", "dark": "深色"}
    THEME_ORDER = ["system", "light", "dark"]

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self.config = config
        self.settings = config.load_settings()
        self.presets = config.load_presets()
        self.active_preset = str(self.settings.get("active_preset") or "builtin_balanced")
        if self.active_preset not in self.presets:
            self.active_preset = "builtin_balanced"

        self.theme = ThemeManager(QApplication.instance(), str(self.settings.get("theme", "system")))
        self.theme.apply()
        self.runner = ServerRunner(self)
        self.health = HealthChecker(self)

        self._log_entries: list[tuple[str, str, str]] = []
        self._elapsed = QElapsedTimer()
        self._uptime_timer = QTimer(self)
        self._uptime_timer.setInterval(1000)
        self._uptime_timer.timeout.connect(self._update_uptime)

        self._build_ui()
        self._connect_signals()
        self._restore_settings()
        self._update_command_preview()
        self._set_running_ui(False)
        self.setWindowTitle(f"llama.cpp Launcher  v{__version__}")
        self.resize(1320, 880)
        self.setMinimumSize(1060, 720)

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(11)
        root.addWidget(self._build_app_bar())

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.addWidget(self._build_left_panel())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(9)
        right_layout.addWidget(self._build_launch_card())
        right_layout.addWidget(self._build_params_card(), 1)
        console = self._build_console_card()
        console.setFixedHeight(190)
        right_layout.addWidget(console)
        body.addWidget(right)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        # 显式指定初始宽度：sizeHint 会被长路径文本撑大，导致分栏出现空白
        body.setSizes([300, 990])
        root.addWidget(body, 1)

        root.addWidget(self._build_action_bar())

    def _build_app_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("AppBar")
        row = QHBoxLayout(frame)
        row.setContentsMargins(18, 13, 16, 13)
        row.setSpacing(13)

        logo = QLabel("L")
        logo.setObjectName("Logo")
        row.addWidget(logo)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        title = QLabel("llama.cpp Launcher")
        title.setObjectName("AppTitle")
        subtitle = QLabel(f"本地大模型服务启动器  ·  v{__version__}  ·  macOS / Windows / Linux")
        subtitle.setObjectName("AppSubtitle")
        texts.addWidget(title)
        texts.addWidget(subtitle)
        row.addLayout(texts, 1)

        self.header_status = QLabel("● 服务未运行")
        self.header_status.setObjectName("StatusPill")
        row.addWidget(self.header_status)

        self.theme_button = make_button(self.THEME_LABELS[self.theme.mode])
        self.theme_button.clicked.connect(self._cycle_theme)
        row.addWidget(self.theme_button)

        download = make_button("下载 llama.cpp")
        download.clicked.connect(open_download_page)
        row.addWidget(download)

        about = make_button("关于")
        about.clicked.connect(self._show_about)
        row.addWidget(about)
        return frame

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)
        self.preset_panel = PresetPanel()
        layout.addWidget(self.preset_panel, 1)

        env_frame, env_layout = card("环境信息")
        env_layout.setSpacing(7)
        env_layout.addLayout(env_row("系统", f"{platform.system()} {platform.release()}"))
        env_layout.addLayout(env_row(
            "配置目录", os.path.basename(self.config.dir) or self.config.dir,
            tooltip=self.config.dir,
        ))
        self.env_enabled = QLabel("")
        self.env_enabled.setObjectName("EnvValue")
        enabled_row = QHBoxLayout()
        enabled_row.addWidget(QLabel("已启用参数"))
        enabled_row.itemAt(0).widget().setObjectName("EnvKey")
        enabled_row.addWidget(self.env_enabled, 1)
        env_layout.addLayout(enabled_row)
        self.env_theme = QLabel("")
        self.env_theme.setObjectName("EnvValue")
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("外观"))
        theme_row.itemAt(0).widget().setObjectName("EnvKey")
        theme_row.addWidget(self.env_theme, 1)
        env_layout.addLayout(theme_row)
        layout.addWidget(env_frame)

        left.setMinimumWidth(250)
        left.setMaximumWidth(340)
        return left

    def _build_launch_card(self) -> QWidget:
        frame, layout = card("启动配置", "路径与模型，启动参数的入口")
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(8)

        self.binary_edit = QLineEdit()
        self.binary_edit.setPlaceholderText(f"留空自动查找 {server_name()}，或手动选择")
        binary_row = field_row("llama-server", self.binary_edit)
        browse_binary = make_button("浏览", "flat")
        browse_binary.setFixedWidth(58)
        browse_binary.clicked.connect(self._browse_binary)
        detect = make_button("自动检测", "flat")
        detect.clicked.connect(self._auto_detect_binary)
        binary_row.addWidget(browse_binary)
        binary_row.addWidget(detect)
        layout.addLayout(binary_row)

        self.binary_status = QLabel("未选择 llama-server")
        self.binary_status.setObjectName("Hint")
        self.binary_status.setWordWrap(True)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("选择 .gguf 模型文件")
        model_row = field_row("模型文件", self.model_edit)
        browse_model = make_button("浏览", "flat")
        browse_model.setFixedWidth(58)
        browse_model.clicked.connect(self._browse_model)
        model_row.addWidget(browse_model)
        layout.addLayout(model_row)

        self.model_status = QLabel("尚未选择模型")
        self.model_status.setObjectName("Hint")
        self.model_status.setWordWrap(True)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(97, 0, 0, 0)
        status_row.setSpacing(14)
        status_row.addWidget(self.binary_status, 1)
        status_row.addWidget(self.model_status, 1)
        layout.addLayout(status_row)

        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("例如：--no-mmap --chat-template chatml")
        self.extra_edit.setToolTip("直接追加到命令末尾，带空格的路径请用引号包裹")
        layout.addLayout(field_row("额外参数", self.extra_edit))

        self.extra_warning = QLabel("")
        self.extra_warning.setObjectName("Warning")
        self.extra_warning.setContentsMargins(97, 0, 0, 0)
        self.extra_warning.hide()
        layout.addWidget(self.extra_warning)
        return frame

    def _build_params_card(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("启动参数")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        self.enabled_badge = QLabel("")
        self.enabled_badge.setObjectName("Badge")
        header.addWidget(self.enabled_badge)
        header.addStretch(1)
        reset = make_button("恢复默认", "flat")
        reset.clicked.connect(self._reset_params)
        header.addWidget(reset)
        layout.addLayout(header)

        self.param_panel = ParamPanel()
        layout.addWidget(self.param_panel, 1)
        return frame

    def _build_console_card(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("控制台")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        clear = make_button("清空日志", "flat")
        clear.clicked.connect(self._clear_log)
        copy = make_button("复制命令", "flat")
        copy.clicked.connect(self._copy_command)
        header.addWidget(clear)
        header.addWidget(copy)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_edit.setPlaceholderText("启动服务后，llama-server 的输出会显示在这里…")
        self.command_edit = QPlainTextEdit()
        self.command_edit.setReadOnly(True)
        self.command_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.tabs.addTab(self.log_edit, "运行日志")
        self.tabs.addTab(self.command_edit, "命令预览")
        layout.addWidget(self.tabs, 1)
        return frame

    def _build_action_bar(self) -> QWidget:
        frame, layout = card()
        layout.setContentsMargins(16, 11, 16, 11)
        row = QHBoxLayout()
        row.setSpacing(9)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("StatusBad")
        self.status_dot.setFixedWidth(14)
        self.status_text = QLabel("服务未运行")
        self.status_text.setObjectName("Muted")
        self.url_label = QLabel("")
        self.url_label.setObjectName("UrlLabel")
        self.uptime_label = QLabel("")
        self.uptime_label.setObjectName("Faint")
        row.addWidget(self.status_dot)
        row.addWidget(self.status_text)
        row.addWidget(self.url_label, 1)
        row.addWidget(self.uptime_label)

        open_web = make_button("打开 WebUI")
        open_web.clicked.connect(self._open_webui)
        self.health_button = make_button("检测服务")
        self.health_button.clicked.connect(self._check_health)
        self.start_button = make_button("启动服务", "primary")
        self.start_button.clicked.connect(self._start_server)
        self.stop_button = make_button("停止服务", "danger")
        self.stop_button.clicked.connect(self._stop_server)
        row.addWidget(open_web)
        row.addWidget(self.health_button)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        layout.addLayout(row)
        return frame

    # ---------------------------------------------------------------- 信号
    def _connect_signals(self) -> None:
        for widget in (self.binary_edit, self.model_edit, self.extra_edit):
            widget.textChanged.connect(self._update_command_preview)
        self.binary_edit.editingFinished.connect(self._refresh_binary_status)
        self.model_edit.editingFinished.connect(self._refresh_model_status)
        self.param_panel.paramsChanged.connect(self._update_command_preview)

        self.preset_panel.apply_requested.connect(self._apply_preset)
        self.preset_panel.save_requested.connect(self._save_as_preset)
        self.preset_panel.overwrite_requested.connect(self._overwrite_preset)
        self.preset_panel.delete_requested.connect(self._delete_preset)
        self.preset_panel.import_requested.connect(self._import_presets)
        self.preset_panel.export_requested.connect(self._export_presets)

        self.runner.output_received.connect(self._append_log)
        self.runner.process_started.connect(self._on_process_started)
        self.runner.process_finished.connect(self._on_process_finished)
        self.runner.process_error.connect(self._on_process_error)
        self.health.result.connect(self._on_health_result)
        self.theme.mode_changed.connect(self._on_theme_changed)
        self.theme.palette_changed.connect(lambda _dark: self._recolor_log())

    # ---------------------------------------------------------------- 设置
    def _restore_settings(self) -> None:
        self.binary_edit.setText(str(self.settings.get("binary_path") or ""))
        self.model_edit.setText(str(self.settings.get("model_path") or ""))
        self.extra_edit.setText(str(self.settings.get("extra_args") or ""))
        self.param_panel.apply_values(self.settings.get("values"))
        self.preset_panel.set_presets(self.presets, self.active_preset)
        self._refresh_binary_status()
        self._refresh_model_status()
        self._on_theme_changed(self.theme.mode)
        geometry_hex = self.settings.get("geometry")
        if geometry_hex:
            try:
                self.restoreGeometry(QByteArray.fromHex(bytes(str(geometry_hex), "ascii")))
            except (TypeError, ValueError):
                pass

    def _collect_settings(self) -> dict:
        settings = dict(self.settings)
        settings.update({
            "theme": self.theme.mode,
            "binary_path": self.binary_edit.text().strip(),
            "model_path": self.model_edit.text().strip(),
            "extra_args": self.extra_edit.text().strip(),
            "values": self.param_panel.values(),
            "active_preset": self.active_preset,
            "geometry": bytes(self.saveGeometry()).hex(),
        })
        return settings

    def closeEvent(self, event) -> None:
        if self.runner.is_running:
            answer = QMessageBox.question(
                self, "服务仍在运行",
                "llama-server 正在运行。退出启动器会一并停止服务，确定退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.stop_and_wait()
        try:
            self.config.save_settings(self._collect_settings())
            self.config.save_custom_presets(self.presets)
        except OSError as error:
            QMessageBox.warning(self, "保存失败", f"配置未能保存：{error}")
        super().closeEvent(event)

    # ---------------------------------------------------------------- 状态
    def _set_status(self, text: str, kind: str = "muted") -> None:
        self.status_text.setText(text)
        self.header_status.setText(f"● {text}")
        names = {"ok": "StatusOk", "bad": "StatusBad", "muted": "Muted"}
        target = names.get(kind, "Muted")
        for label in (self.status_dot, self.status_text):
            label.setObjectName(target)
            label.style().unpolish(label)
            label.style().polish(label)
        self.status_dot.setText("●")

    def _refresh_binary_status(self) -> None:
        path = self.binary_edit.text().strip()
        if path and os.path.isfile(path):
            self.binary_status.setText(f"已选择 · {probe_version(path) or '路径有效'}")
            self.binary_status.setObjectName("StatusOk")
        else:
            auto = find_binary()
            if not path and auto:
                self.binary_edit.setText(auto)
                self.binary_status.setText(f"自动找到 · {probe_version(auto) or auto}")
                self.binary_status.setObjectName("StatusOk")
            else:
                self.binary_status.setText("未找到，请手动选择或把 llama-server 放到程序目录 / bin 目录")
                self.binary_status.setObjectName("Hint")
        self.binary_status.style().unpolish(self.binary_status)
        self.binary_status.style().polish(self.binary_status)

    def _refresh_model_status(self) -> None:
        path = self.model_edit.text().strip()
        if not path:
            self.model_status.setText("尚未选择模型")
            self.model_status.setObjectName("Hint")
        else:
            valid, info = inspect_model(path)
            self.model_status.setText(("已就绪 · " if valid else "") + info)
            self.model_status.setObjectName("StatusOk" if valid else "StatusBad")
        self.model_status.style().unpolish(self.model_status)
        self.model_status.style().polish(self.model_status)

    def _set_running_ui(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.health_button.setText("检测服务" if running else "检测服务（需先启动）")
        if not running:
            self.uptime_label.setText("")

    def _on_process_started(self) -> None:
        self._set_status("服务运行中", "ok")
        self._set_running_ui(True)
        self.url_label.setText(self._url())
        self._elapsed.start()
        self._uptime_timer.start()
        self._update_uptime()
        self._append_log("[启动器] 进程已启动，等待服务就绪…", "ok")

    def _update_uptime(self) -> None:
        if not self.runner.is_running:
            return
        seconds = self._elapsed.elapsed() // 1000
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        self.uptime_label.setText(f"运行 {hours:02d}:{minutes:02d}:{secs:02d}")

    def _on_theme_changed(self, mode: str) -> None:
        self.theme_button.setText(self.THEME_LABELS[mode])
        if hasattr(self, "env_theme"):
            self.env_theme.setText(self.THEME_LABELS[mode])

    # ---------------------------------------------------------------- 参数与命令
    def current_command(self) -> list[str]:
        binary = self.binary_edit.text().strip() or "<llama-server>"
        return build_command(
            binary, self.model_edit.text().strip(),
            self.param_panel.values(), self.extra_edit.text().strip(),
        )

    def _update_command_preview(self) -> None:
        self.command_edit.setPlainText(shell_join(self.current_command()))
        _extra, error = parse_extra_args(self.extra_edit.text())
        self.extra_warning.setText(error)
        self.extra_warning.setVisible(bool(error))
        count = self.param_panel.enabled_count()
        self.enabled_badge.setText(f"{count} / {len(SPECS)} 项已启用")
        self.env_enabled.setText(f"{count} / {len(SPECS)}")

    def _copy_command(self) -> None:
        QApplication.clipboard().setText(self.command_edit.toPlainText())
        self._set_status_text("启动命令已复制到剪贴板")

    def _set_status_text(self, message: str) -> None:
        self.statusBar().showMessage(message, 3000)

    def _reset_params(self) -> None:
        answer = QMessageBox.question(
            self, "恢复默认", "确定把所有参数恢复为默认值吗？路径与额外参数不受影响。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.param_panel.reset()
            self._append_log("[启动器] 参数已恢复默认")

    # ---------------------------------------------------------------- 日志
    @staticmethod
    def _classify(text: str) -> str:
        lower = text.lower()
        if "error" in lower or "failed" in lower or "fatal" in lower or "unrecognised" in lower:
            return "bad"
        if "warn" in lower:
            return "warn"
        if "listening" in lower or "started" in lower or "ready" in lower or "已启动" in text:
            return "ok"
        if text.startswith("[启动器]"):
            return "accent"
        return "text"

    def _append_log(self, text: str, level: str = "auto") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        resolved = self._classify(text) if level == "auto" else level
        self._log_entries.append((stamp, resolved, text))
        if len(self._log_entries) > MAX_LOG_LINES:
            del self._log_entries[: len(self._log_entries) - MAX_LOG_LINES]
            self._recolor_log()
            return
        self._render_log_line(stamp, resolved, text)

    def _log_color(self, level: str) -> str:
        c = self.theme.colors
        return {
            "bad": c["danger"], "warn": c["warning"], "ok": c["success"],
            "accent": c["accent"], "text": c["text"],
        }.get(level, c["text"])

    def _render_log_line(self, stamp: str, level: str, text: str) -> None:
        cursor = self.log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        time_fmt = QTextCharFormat()
        time_fmt.setForeground(QColor(self.theme.colors["faint"]))
        cursor.setCharFormat(time_fmt)
        cursor.insertText(f"[{stamp}] ")
        text_fmt = QTextCharFormat()
        text_fmt.setForeground(QColor(self._log_color(level)))
        cursor.setCharFormat(text_fmt)
        cursor.insertText(text + "\n")
        self.log_edit.setTextCursor(cursor)
        self.log_edit.ensureCursorVisible()

    def _recolor_log(self) -> None:
        self.log_edit.clear()
        for stamp, level, text in self._log_entries:
            self._render_log_line(stamp, level, text)

    def _clear_log(self) -> None:
        self._log_entries.clear()
        self.log_edit.clear()

    # ---------------------------------------------------------------- 预设
    def _current_preset_data(self) -> dict:
        return {
            "values": self.param_panel.values(),
            "extra_args": self.extra_edit.text().strip(),
        }

    def _apply_preset(self, key: str) -> None:
        preset = self.presets.get(key)
        if not preset:
            return
        self.param_panel.apply_values(preset.get("values"))
        self.extra_edit.setText(str(preset.get("extra_args") or ""))
        self.active_preset = key
        self.preset_panel.set_presets(self.presets, key)
        self._append_log(f"[启动器] 已应用预设：{preset.get('name')}", "accent")
        self._set_status_text(f"已应用预设：{preset.get('name')}")

    def _save_as_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "另存为预设", "预设名称：", text="我的配置")
        if not ok or not name.strip():
            return
        description, ok2 = QInputDialog.getText(
            self, "预设说明", "用一句话描述这个预设（可留空）：", text=""
        )
        preset_id = self.config.new_preset_id()
        self.presets[preset_id] = {
            "name": name.strip(), "description": description.strip() if ok2 else "",
            "builtin": False, **self._current_preset_data(),
        }
        self.active_preset = preset_id
        self.preset_panel.set_presets(self.presets, preset_id)
        self._persist_presets()

    def _overwrite_preset(self, key: str) -> None:
        preset = self.presets.get(key)
        if not preset or preset.get("builtin"):
            QMessageBox.information(self, "内置预设", "内置预设不可覆盖，请使用「另存为新预设」。")
            return
        answer = QMessageBox.question(
            self, "覆盖预设", f"确定用当前参数覆盖「{preset['name']}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        preset.update(self._current_preset_data())
        self.preset_panel.set_presets(self.presets, key)
        self._persist_presets()
        self._set_status_text("预设已更新")

    def _delete_preset(self, key: str) -> None:
        preset = self.presets.get(key)
        if not preset or preset.get("builtin"):
            QMessageBox.information(self, "内置预设", "内置预设不可删除。")
            return
        answer = QMessageBox.question(
            self, "删除预设", f"确定删除「{preset['name']}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.presets.pop(key, None)
        if self.active_preset == key:
            self.active_preset = "builtin_balanced"
            self._apply_preset(self.active_preset)
        else:
            self.preset_panel.set_presets(self.presets, self.active_preset)
        self._persist_presets()

    def _persist_presets(self) -> None:
        try:
            self.config.save_custom_presets(self.presets)
        except OSError as error:
            QMessageBox.warning(self, "保存失败", f"预设未能保存：{error}")

    def _export_presets(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出自定义预设", "llama-launcher-presets.json", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            count = self.config.export_presets(self.presets, path)
            self._set_status_text(f"已导出 {count} 个自定义预设")
        except OSError as error:
            QMessageBox.warning(self, "导出失败", str(error))

    def _import_presets(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入预设", "", "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            imported = self.config.import_presets(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "导入失败", str(error))
            return
        first_key = ""
        for key, preset in imported:
            self.presets[key] = preset
            if not first_key:
                first_key = key
        self.active_preset = first_key
        self.preset_panel.set_presets(self.presets, first_key)
        self._persist_presets()
        self._set_status_text(f"已导入 {len(imported)} 个预设")

    # ---------------------------------------------------------------- 文件选择
    def _browse_binary(self) -> None:
        start = self.binary_edit.text().strip() or self.settings.get("last_binary_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 llama-server 可执行文件", start,
            f"{server_name()} ({server_name()});;所有文件 (*)",
        )
        if path:
            self.settings["last_binary_dir"] = os.path.dirname(path)
            self.binary_edit.setText(path)
            self._refresh_binary_status()

    def _auto_detect_binary(self) -> None:
        found = find_binary(self.binary_edit.text().strip())
        if found:
            self.binary_edit.setText(found)
            self._refresh_binary_status()
            self._set_status_text(f"找到 llama-server：{found}")
        else:
            QMessageBox.warning(
                self, "未找到 llama-server",
                "请确认已下载 llama.cpp 并编译，或把 llama-server 放到程序目录 / bin 目录。",
            )

    def _browse_model(self) -> None:
        start = self.model_edit.text().strip() or self.settings.get("last_model_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 GGUF 模型", start, "GGUF 模型 (*.gguf);;所有文件 (*)"
        )
        if path:
            self.settings["last_model_dir"] = os.path.dirname(path)
            self.model_edit.setText(path)
            self._refresh_model_status()

    # ---------------------------------------------------------------- 运行控制
    def _start_server(self) -> None:
        if self.runner.is_running:
            return
        binary = self.binary_edit.text().strip()
        if not binary or not os.path.isfile(binary):
            QMessageBox.warning(self, "无法启动", "请选择有效的 llama-server 可执行文件。")
            return
        model = self.model_edit.text().strip()
        valid, info = inspect_model(model)
        if not valid:
            QMessageBox.warning(self, "无法启动", f"模型无效：{info}")
            return

        _extra, extra_error = parse_extra_args(self.extra_edit.text())
        if extra_error:
            QMessageBox.warning(self, "额外参数有误", extra_error)
            return

        values = normalize_values(self.param_panel.values())
        host = str(values.get("host") or "127.0.0.1")
        port = int(values.get("port") or 8080)
        ok, port_error = port_available(host, port)
        if not ok:
            answer = QMessageBox.question(
                self, "端口可能被占用", f"{port_error}\n仍要尝试启动吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        command = self.current_command()
        self._clear_log()
        self._append_log("[启动器] " + shell_join(command), "accent")
        self.tabs.setCurrentIndex(0)
        self._set_status("正在启动…", "muted")
        if not self.runner.start(command, working_dir=os.path.dirname(os.path.abspath(binary))):
            self._set_status("启动失败", "bad")

    def _stop_server(self) -> None:
        if not self.runner.is_running:
            return
        self._append_log("[启动器] 正在停止服务…", "accent")
        self.runner.stop()
        self._set_status("正在停止…", "muted")

    def _on_process_finished(self, code: int, status: str) -> None:
        self._uptime_timer.stop()
        self._append_log(f"[启动器] 进程结束：{status}（退出码 {code}）", "ok" if code == 0 else "bad")
        self._set_status(f"服务已停止（退出码 {code}）", "bad" if code else "muted")
        self._set_running_ui(False)

    def _on_process_error(self, message: str) -> None:
        self._append_log("[启动器] " + message, "bad")
        self._set_status("启动失败", "bad")
        self._set_running_ui(False)

    def _url(self) -> str:
        values = normalize_values(self.param_panel.values())
        host = str(values.get("host") or "127.0.0.1")
        try:
            port = int(values.get("port") or 8080)
        except (TypeError, ValueError):
            port = 8080
        return server_url(host, port)

    def _open_webui(self) -> None:
        QDesktopServices.openUrl(QUrl(self._url()))

    def _check_health(self) -> None:
        self._set_status("正在检测服务…", "muted")
        self.health.check(self._url() + "/health")

    def _on_health_result(self, ok: bool, message: str) -> None:
        self._append_log(f"[启动器] 健康检查：{message}", "ok" if ok else "bad")
        if ok:
            self._set_status("服务就绪", "ok")
        else:
            self._set_status(f"服务不可达：{message}", "bad")
        self.url_label.setText(self._url())

    # ---------------------------------------------------------------- 杂项
    def _cycle_theme(self) -> None:
        index = self.THEME_ORDER.index(self.theme.mode)
        next_mode = self.THEME_ORDER[(index + 1) % len(self.THEME_ORDER)]
        self.theme.apply(next_mode)
        self._set_status_text(f"主题已切换：{self.THEME_LABELS[next_mode]}")

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "关于 llama.cpp Launcher",
            f"<b>llama.cpp Launcher v{__version__}</b><br><br>"
            "跨平台 llama.cpp 图形启动器：<br>"
            "• macOS / Windows / Linux<br>"
            "• 结构化启动参数、搜索与启用态管理<br>"
            "• 参数预设（含导入 / 导出）与深浅色主题<br>"
            "• 实时日志、健康检查、端口预检与单实例保护<br><br>"
            f"系统：{platform.system()} {platform.release()}<br>"
            f"配置目录：{self.config.dir}<br>"
            f"崩溃日志：{self.config.crash_log_path}",
        )
