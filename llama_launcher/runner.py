"""llama-server 进程管理：启动、日志读取、优雅停止与健康检查。"""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, QProcess, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


def normalize_host(host: str) -> str:
    host = (host or "127.0.0.1").strip()
    if host in {"0.0.0.0", "::", "*"}:
        return "127.0.0.1"
    return host


def server_url(host: str, port: int) -> str:
    host = normalize_host(host)
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{int(port)}"


class ServerRunner(QObject):
    """用 QProcess 异步运行 llama-server，跨平台且不阻塞界面。"""

    output_received = Signal(str)
    process_started = Signal()
    process_finished = Signal(int, str)
    process_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.process: QProcess | None = None
        self._buffer = ""
        self._started_emitted = False
        self._stopping = False
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._force_kill)

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def start(self, command: list[str], working_dir: str = "") -> bool:
        if self.is_running or not command or not command[0]:
            return False
        self._buffer = ""
        self._started_emitted = False
        self._stopping = False

        process = QProcess(self)
        process.setProgram(command[0])
        process.setArguments(command[1:])
        if working_dir and os.path.isdir(working_dir):
            process.setWorkingDirectory(working_dir)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.stateChanged.connect(self._on_state_changed)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

        self.process = process
        process.start()
        return True

    def stop(self) -> None:
        """异步优雅停止：先 terminate，3 秒后仍存活则 kill。"""
        if not self.is_running or self.process is None:
            return
        self._stopping = True
        self.process.terminate()
        self._kill_timer.start(3000)

    def stop_and_wait(self, timeout_ms: int = 5000) -> bool:
        """退出程序前同步停止，确保不留孤儿进程。仅用于关闭流程。"""
        self._kill_timer.stop()
        process = self.process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return True
        self._stopping = True
        process.terminate()
        if not process.waitForFinished(max(1000, timeout_ms // 2)):
            process.kill()
            process.waitForFinished(max(1000, timeout_ms // 2))
        return process.state() == QProcess.ProcessState.NotRunning

    def _force_kill(self) -> None:
        if self.is_running and self.process is not None:
            self.process.kill()

    def _read_stdout(self) -> None:
        if self.process is not None:
            self._drain(bytes(self.process.readAllStandardOutput()))

    def _read_stderr(self) -> None:
        if self.process is not None:
            self._drain(bytes(self.process.readAllStandardError()))

    def _drain(self, data: bytes) -> None:
        if not data:
            return
        self._buffer += data.decode("utf-8", errors="replace")
        lines = self._buffer.splitlines()
        if self._buffer.endswith(("\n", "\r")):
            self._buffer = ""
        else:
            self._buffer = lines.pop() if lines else self._buffer
        for line in lines:
            self.output_received.emit(line.rstrip())

    def _on_state_changed(self, state: QProcess.ProcessState) -> None:
        if state == QProcess.ProcessState.Running and not self._started_emitted:
            self._started_emitted = True
            self.process_started.emit()

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._kill_timer.stop()
        if self._buffer.strip():
            self.output_received.emit(self._buffer.rstrip())
            self._buffer = ""
        status = "正常退出" if exit_status == QProcess.ExitStatus.NormalExit else "异常退出"
        if self._stopping:
            status = "已停止"
        self._stopping = False

        process = self.process
        self.process = None
        if process is not None:
            process.deleteLater()
        self.process_finished.emit(exit_code, status)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        messages = {
            QProcess.ProcessError.FailedToStart: "无法启动进程，请检查 llama-server 路径与执行权限。",
            QProcess.ProcessError.Crashed: "llama-server 意外崩溃。",
            QProcess.ProcessError.TimedOut: "进程等待超时。",
            QProcess.ProcessError.WriteError: "写入进程 stdin 失败。",
            QProcess.ProcessError.ReadError: "读取进程输出失败。",
        }
        self.process_error.emit(messages.get(error, f"进程错误：{error.name if hasattr(error, 'name') else error}"))


class HealthChecker(QObject):
    """异步探测 /health 端点，避免阻塞 UI。"""

    result = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_finished)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._reply: QNetworkReply | None = None
        self._generation = 0

    def check(self, url: str, timeout_ms: int = 4000) -> None:
        self.cancel()
        self._generation += 1
        request = QNetworkRequest(QUrl(url))
        self._reply = self._manager.get(request)
        self._timer.start(timeout_ms)

    def cancel(self) -> None:
        self._timer.stop()
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _on_finished(self, reply: QNetworkReply) -> None:
        if reply is not self._reply:
            reply.deleteLater()
            return
        self._timer.stop()
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        message = f"HTTP {status}" if status else ("服务可访问" if ok else reply.errorString())
        self._reply = None
        reply.deleteLater()
        self.result.emit(bool(ok), str(message))

    def _on_timeout(self) -> None:
        self.cancel()
        self.result.emit(False, "检测超时")
