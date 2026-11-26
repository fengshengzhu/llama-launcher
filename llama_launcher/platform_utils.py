"""平台相关工具：查找 llama-server、校验模型、检测端口、打开下载页。"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import webbrowser
from typing import Iterable

RELEASE_URL = "https://github.com/ggml-org/llama.cpp/releases"
GGUF_MAGIC = b"GGUF"


def server_name() -> str:
    return "llama-server.exe" if platform.system() == "Windows" else "llama-server"


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and (platform.system() == "Windows" or os.access(path, os.X_OK))


def candidate_paths(configured: str = "") -> list[str]:
    """按优先级返回可能的 llama-server 路径。"""
    name = server_name()
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    candidates: list[str] = []

    def add(path: str) -> None:
        if path and path not in candidates:
            candidates.append(os.path.normpath(os.path.expanduser(path)))

    add(configured)
    add(os.environ.get("LLAMA_SERVER_PATH", ""))
    add(os.environ.get("LLAMA_CPP_PATH", ""))
    if os.environ.get("LLAMA_CPP_PATH"):
        add(os.path.join(os.environ["LLAMA_CPP_PATH"], "build", "bin", name))

    for base in (os.getcwd(), project_root, os.path.dirname(sys.executable)):
        add(os.path.join(base, name))
        add(os.path.join(base, "bin", name))
        add(os.path.join(base, "llama.cpp", "build", "bin", name))

    found = shutil.which("llama-server") or shutil.which(name)
    if found:
        add(found)

    system = platform.system()
    home = os.path.expanduser("~")
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        for base in (local, os.environ.get("ProgramFiles", "C:\\Program Files")):
            add(os.path.join(base, "Programs", "llama.cpp", name))
            add(os.path.join(base, "llama.cpp", name))
        add(os.path.join("C:\\", "llama.cpp", "build", "bin", name))
    elif system == "Darwin":
        for base in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
            add(os.path.join(base, name))
        add(os.path.join(home, "llama.cpp", "build", "bin", name))
        add(os.path.join(home, "Downloads", "llama.cpp", "build", "bin", name))
    else:
        for base in ("/usr/local/bin", "/usr/bin", "/opt/bin"):
            add(os.path.join(base, name))
        add(os.path.join(home, "llama.cpp", "build", "bin", name))
        add(os.path.join(home, ".local", "bin", name))

    return candidates


def find_binary(configured: str = "") -> str:
    for path in candidate_paths(configured):
        if _is_executable(path):
            return path
    return ""


def probe_version(path: str) -> str:
    """执行 `llama-server --version`，返回第一行有效输出。"""
    if not _is_executable(path):
        return ""
    flags = 0
    if platform.system() == "Windows":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=6, creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return "已找到可执行文件（版本信息不可用）"
    for line in ((result.stdout or "") + "\n" + (result.stderr or "")).splitlines():
        line = line.strip()
        if line:
            return line[:160]
    return "已找到可执行文件（版本信息不可用）"


def is_gguf(path: str) -> bool:
    return bool(path) and os.path.isfile(path) and path.lower().endswith(".gguf")


def inspect_model(path: str) -> tuple[bool, str]:
    """校验 GGUF 文件头，返回 (是否有效, 描述)。避免改名文件骗过启动器。"""
    if not path or not os.path.isfile(path):
        return False, "模型文件不存在"
    if not path.lower().endswith(".gguf"):
        return False, "文件后缀不是 .gguf"
    try:
        size = os.path.getsize(path)
        if size < 16:
            return False, "文件过小，不是有效 GGUF"
        with open(path, "rb") as handle:
            magic = handle.read(4)
        if magic != GGUF_MAGIC:
            return False, "文件头不是 GGUF 标识，可能已损坏或格式不对"
        return True, f"{os.path.basename(path)} · {size / (1024 ** 3):.2f} GB"
    except OSError as error:
        return False, f"读取模型失败：{error}"


def port_available(host: str, port: int) -> tuple[bool, str]:
    """启动前探测端口是否可绑定，避免 llama-server 启动后才报地址占用。"""
    host = (host or "127.0.0.1").strip()
    if host in {"0.0.0.0", "*", "::"}:
        host = "0.0.0.0"
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((host, int(port)))
        return True, ""
    except (OSError, ValueError, OverflowError) as error:
        return False, f"端口 {port} 不可用：{error}"


def open_download_page() -> None:
    webbrowser.open(RELEASE_URL)


def unique_existing(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if path not in seen and os.path.exists(path):
            seen.add(path)
            result.append(path)
    return result
