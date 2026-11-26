"""llama.cpp Launcher 入口：python main.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from datetime import datetime

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QMessageBox

from llama_launcher import __version__
from llama_launcher.config import ConfigManager
from llama_launcher.ui.main_window import MainWindow

INSTANCE_KEY = "LlamaLauncher.SingleInstance.v1"


def _log_crash(text: str) -> str:
    try:
        path = ConfigManager().crash_log_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} =====\n{text}\n")
        return path
    except OSError:
        return ""


def _install_exception_hook() -> None:
    def hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        path = _log_crash(text)
        if sys.stderr is not None:  # 窗口模式下 stderr 可能为 None
            try:
                sys.stderr.write(text)
            except (OSError, ValueError):
                pass
        try:
            QMessageBox.critical(
                None, "启动器发生异常",
                "程序遇到未处理的错误，已记录日志。\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                + (f"日志文件：{path}" if path else "日志写入失败，请查看控制台输出"),
            )
        except Exception:
            pass

    sys.excepthook = hook


def _self_test() -> int:
    """离屏构造完整界面，供打包后的 exe 做启动验证。"""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="llama-launcher-selftest-")
    app = QApplication(sys.argv)
    window = MainWindow(ConfigManager())
    window.show()
    app.processEvents()
    command = window.current_command()
    result = {
        "ok": True,
        "version": __version__,
        "title": window.windowTitle(),
        "params": len(window.param_panel.rows),
        "presets": len(window.presets),
        "command_has_no_public_flag": "--public" not in command,
        "preview": window.command_edit.toPlainText()[:300],
    }
    output = os.environ.get("LLAMA_LAUNCHER_SELFTEST_FILE")
    if output:
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()

    app = QApplication(sys.argv)
    app.setApplicationName("llama.cpp Launcher")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("LlamaLauncher")
    _install_exception_hook()

    # 单实例：避免多开各自抢占同一端口
    guard = QSharedMemory(INSTANCE_KEY)
    if not guard.create(1):
        QMessageBox.information(None, "已在运行", "llama.cpp Launcher 已经在运行中。")
        return 0

    try:
        window = MainWindow(ConfigManager())
        window.show()
        return app.exec()
    except Exception:  # noqa: BLE001 - 兜底，确保窗口模式 exe 也能留下错误痕迹
        text = traceback.format_exc()
        path = _log_crash(text)
        QMessageBox.critical(None, "启动失败", f"{text}\n日志：{path}" if path else text)
        return 1


if __name__ == "__main__":
    sys.exit(main())
