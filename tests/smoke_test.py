"""核心功能 + 主窗口冒烟测试：python tests/smoke_test.py"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="llama-launcher-test-")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from llama_launcher import params as P  # noqa: E402
from llama_launcher.config import ConfigManager  # noqa: E402
from llama_launcher.params import (  # noqa: E402
    build_command, default_values, normalize_values, parse_extra_args, shell_join,
)
from llama_launcher.platform_utils import inspect_model, port_available  # noqa: E402
from llama_launcher.runner import HealthChecker, ServerRunner, server_url  # noqa: E402
from llama_launcher.theme import ThemeManager  # noqa: E402
from llama_launcher.ui.main_window import MainWindow  # noqa: E402


def test_command() -> None:
    values = default_values()
    command = build_command("llama-server", "/models/model.gguf", values, "--no-mmap")
    assert command[0] == "llama-server"
    assert command[1:3] == ["-m", "/models/model.gguf"]
    assert "-c" in command and "8192" in command
    assert "--host" in command and "127.0.0.1" in command
    assert command[-1] == "--no-mmap"
    assert "model.gguf" in shell_join(command)
    assert "--public" not in command
    assert all(spec.flag != "--public" for spec in P.SPECS)
    assert "-np" in command and "-fa" not in command  # 默认不启用 FA


def test_number_format_and_quoting() -> None:
    values = default_values()
    values["rope_freq_base"] = 1e12
    values["rope_freq_base__enabled"] = True
    command = build_command("llama-server", "m.gguf", values)
    assert "1000000000000" in command, command
    assert not any("e+" in part for part in command)
    assert shell_join(["prog", "C:\\Program Files\\app.exe"]).startswith("prog")


def test_normalize_values_is_defensive() -> None:
    broken = {"port": "abc", "ctx_size": 999999999, "temp": "not-a-float",
              "flash_attn": "invalid", "api_key": 12345, "port__enabled": "yes"}
    values = normalize_values(broken)
    assert values["port"] == 8080
    assert values["ctx_size"] == 1048576
    assert values["temp"] == 0.8
    assert values["flash_attn"] == ""
    assert values["api_key"] == "12345"
    assert values["port__enabled"] is True


def test_extra_args_errors() -> None:
    assert parse_extra_args("--no-mmap --foo bar")[0] == ["--no-mmap", "--foo", "bar"]
    assert parse_extra_args('--path "unterminated')[1]


def test_gguf_and_port() -> None:
    directory = tempfile.mkdtemp(prefix="llama-gguf-")
    good = os.path.join(directory, "model.gguf")
    with open(good, "wb") as handle:
        handle.write(b"GGUF" + b"\x00" * 64)
    assert inspect_model(good)[0] is True

    bad = os.path.join(directory, "broken.gguf")
    with open(bad, "wb") as handle:
        handle.write(b"NOT!" + b"\x00" * 64)
    assert inspect_model(bad)[0] is False
    assert inspect_model(os.path.join(directory, "missing.gguf"))[0] is False

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        assert port_available("127.0.0.1", port)[0] is False
    assert port_available("127.0.0.1", 0)[0] is True


def test_config_and_presets() -> None:
    manager = ConfigManager()
    settings = manager.load_settings()
    assert settings["theme"] == "system"
    assert len(settings["values"]) > 40
    presets = manager.load_presets()
    assert len(presets) == 5
    assert presets["builtin_longctx"]["values"]["ctx_size"] == 65536
    assert presets["builtin_api"]["values"]["api_key"] == ""  # 不再内置硬编码密钥

    presets["custom_test"] = {
        "name": "测试预设", "description": "导出用", "builtin": False,
        "values": default_values(), "extra_args": "--no-mmap",
    }
    export_path = os.path.join(tempfile.mkdtemp(prefix="llama-export-"), "presets.json")
    assert manager.export_presets(presets, export_path) == 1
    imported = manager.import_presets(export_path)
    assert len(imported) == 1 and imported[0][1]["extra_args"] == "--no-mmap"
    with open(os.path.join(ROOT, "tests", "_broken.json"), "w", encoding="utf-8") as handle:
        json.dump({"bad": True}, handle)
    try:
        manager.import_presets(os.path.join(ROOT, "tests", "_broken.json"))
    except ValueError:
        pass
    else:
        raise AssertionError("损坏的预设文件应被拒绝")
    finally:
        os.unlink(os.path.join(ROOT, "tests", "_broken.json"))


def main() -> None:
    test_command()
    test_number_format_and_quoting()
    test_normalize_values_is_defensive()
    test_extra_args_errors()
    test_gguf_and_port()
    test_config_and_presets()
    assert server_url("0.0.0.0", 8080) == "http://127.0.0.1:8080"

    app = QApplication([])
    theme = ThemeManager(app)
    theme.apply("dark")
    assert theme.is_dark
    theme.apply("light")
    assert not theme.is_dark

    window = MainWindow(ConfigManager())
    window.show()
    assert window.param_panel.values()["port"] == 8080
    assert window.param_panel.enabled_count() > 0
    window.param_panel.apply_values({"ctx_size": 32768, "ctx_size__enabled": True})
    assert window.param_panel.values()["ctx_size"] == 32768
    window.param_panel.reset()
    assert window.param_panel.values()["ctx_size"] == 8192

    window._apply_preset("builtin_longctx")
    assert window.param_panel.values()["ctx_size"] == 65536
    assert "--public" not in window.current_command()
    assert window._url() == "http://127.0.0.1:8080"

    window._append_log("hello error", "bad")
    before = len(window._log_entries)
    window.theme.apply("dark")
    assert len(window._log_entries) == before
    assert window.log_edit.toPlainText().strip()
    window.theme.apply("light")

    runner = ServerRunner()
    output: list[str] = []
    runner.output_received.connect(output.append)
    loop = QEventLoop()
    runner.process_finished.connect(lambda *_: loop.quit())
    runner.process_error.connect(lambda *_: loop.quit())
    runner.start([sys.executable, "-c", "print('hello-from-server')"])
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert any("hello-from-server" in line for line in output), output
    assert not runner.is_running

    health = HealthChecker()
    health_result: list[tuple[bool, str]] = []
    health.result.connect(lambda ok, message: health_result.append((ok, message)))
    health_loop = QEventLoop()
    health.result.connect(lambda *_: health_loop.quit())
    health.check("http://127.0.0.1:1/health")
    QTimer.singleShot(5000, health_loop.quit)
    health_loop.exec()
    assert len(health_result) == 1, health_result

    app.quit()
    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
