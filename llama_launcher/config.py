"""跨平台配置与预设持久化（纯 JSON，无第三方依赖）。"""

from __future__ import annotations

import json
import os
import platform
import tempfile
import uuid
from copy import deepcopy
from typing import Any

from .params import default_values, normalize_values


APP_DIR_NAME = "LlamaLauncher"
PRESET_FORMAT = "llama-launcher-presets"


def config_dir() -> str:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        return os.path.join(base, APP_DIR_NAME)
    if system == "Darwin":
        return os.path.expanduser("~/Library/Application Support/" + APP_DIR_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "llama-launcher")


def _with_params(**updates: Any) -> dict[str, Any]:
    values = default_values()
    for key, value in updates.items():
        values[key] = value
        enable_key = f"{key}__enabled"
        if enable_key in values:
            values[enable_key] = bool(value) if isinstance(value, (str, bool)) else True
    return values


def builtin_presets() -> dict[str, dict[str, Any]]:
    """内置预设。key 稳定，升级时不会被用户数据覆盖。"""
    return {
        "builtin_balanced": {
            "name": "均衡通用",
            "description": "适合大多数 7B / 14B 模型的日常对话与 API 调用。",
            "values": default_values(),
            "extra_args": "",
            "builtin": True,
        },
        "builtin_lowvram": {
            "name": "低显存 / CPU",
            "description": "关闭 GPU 卸载、缩短上下文并量化 KV 缓存，适合内存有限的机器。",
            "values": _with_params(
                ctx_size=4096, n_gpu_layers=0, batch_size=256, ubatch_size=256,
                cache_type_k="q8_0", cache_type_v="q8_0", temp=0.7,
            ),
            "extra_args": "",
            "builtin": True,
        },
        "builtin_gpu": {
            "name": "高性能 GPU",
            "description": "全层卸载 + Flash Attention + 大批处理，发挥独显性能。",
            "values": _with_params(
                ctx_size=16384, n_gpu_layers=99, flash_attn="on",
                batch_size=1024, ubatch_size=512, threads=8, threads_batch=8,
            ),
            "extra_args": "",
            "builtin": True,
        },
        "builtin_longctx": {
            "name": "长上下文",
            "description": "64K 上下文，配合 Flash Attention 与 q8 KV 缓存降低显存占用。",
            "values": _with_params(
                ctx_size=65536, n_gpu_layers=99, flash_attn="on",
                cache_type_k="q8_0", cache_type_v="q8_0",
                batch_size=1024, ubatch_size=512,
            ),
            "extra_args": "",
            "builtin": True,
        },
        "builtin_api": {
            "name": "OpenAI 兼容 API",
            "description": "监听 0.0.0.0、4 路并行、关闭 WebUI、启用 Jinja 模板。"
                           "对外开放前请在「服务」页设置 API Key。",
            "values": _with_params(
                host="0.0.0.0", port=8080, parallel=4, jinja=True,
                no_webui=True, temp=0.7,
            ),
            "extra_args": "",
            "builtin": True,
        },
    }


DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "system",
    "binary_path": "",
    "model_path": "",
    "extra_args": "",
    "active_preset": "builtin_balanced",
    "values": default_values(),
    "geometry": None,
    "last_model_dir": "",
    "last_binary_dir": "",
}


def _read_json(path: str, fallback: Any) -> Any:
    if not os.path.isfile(path):
        return deepcopy(fallback)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError, UnicodeError):
        return deepcopy(fallback)


def _write_json(path: str, payload: Any) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".llama-launcher-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


class ConfigManager:
    def __init__(self) -> None:
        self.dir = config_dir()
        self.settings_path = os.path.join(self.dir, "settings.json")
        self.presets_path = os.path.join(self.dir, "presets.json")
        self.crash_log_path = os.path.join(self.dir, "crash.log")

    # ---------- 设置 ----------
    def load_settings(self) -> dict[str, Any]:
        raw = _read_json(self.settings_path, DEFAULT_SETTINGS)
        if not isinstance(raw, dict):
            raw = {}
        settings = deepcopy(DEFAULT_SETTINGS)
        for key, value in raw.items():
            if key in settings and key != "values":
                settings[key] = value
        if settings.get("theme") not in {"system", "light", "dark"}:
            settings["theme"] = "system"
        if not isinstance(settings.get("geometry"), str):
            settings["geometry"] = None
        settings["values"] = normalize_values(raw.get("values"))
        return settings

    def save_settings(self, settings: dict[str, Any]) -> None:
        _write_json(self.settings_path, settings)

    # ---------- 预设 ----------
    def load_presets(self) -> dict[str, dict[str, Any]]:
        raw = _read_json(self.presets_path, {})
        result = builtin_presets()
        if isinstance(raw, dict):
            for key, preset in raw.items():
                if not isinstance(preset, dict) or key in result:
                    continue
                result[key] = self._sanitize_custom(key, preset)
        return result

    @staticmethod
    def _sanitize_custom(key: str, preset: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": str(preset.get("name") or "未命名预设")[:60],
            "description": str(preset.get("description") or "")[:300],
            "values": normalize_values(preset.get("values")),
            "extra_args": str(preset.get("extra_args") or "")[:2000],
            "builtin": False,
        }

    def save_custom_presets(self, presets: dict[str, dict[str, Any]]) -> None:
        custom = {
            key: {k: v for k, v in preset.items() if k != "builtin"}
            for key, preset in presets.items()
            if isinstance(preset, dict) and not preset.get("builtin")
        }
        _write_json(self.presets_path, custom)

    # ---------- 预设导入 / 导出 ----------
    @staticmethod
    def export_presets(presets: dict[str, dict[str, Any]], path: str) -> int:
        """导出自定义预设，返回导出数量。"""
        items = [
            {
                "name": preset.get("name", "未命名预设"),
                "description": preset.get("description", ""),
                "values": normalize_values(preset.get("values")),
                "extra_args": preset.get("extra_args", ""),
            }
            for preset in presets.values()
            if isinstance(preset, dict) and not preset.get("builtin")
        ]
        _write_json(path, {"format": PRESET_FORMAT, "version": 1, "presets": items})
        return len(items)

    def import_presets(self, path: str) -> list[tuple[str, dict[str, Any]]]:
        """读取预设文件，返回 [(新 id, 预设)]；格式错误抛出异常。"""
        payload = _read_json(path, None)
        if not isinstance(payload, dict) or payload.get("format") != PRESET_FORMAT:
            raise ValueError("不是有效的预设文件")
        items = payload.get("presets")
        if not isinstance(items, list):
            raise ValueError("预设文件内容格式错误")
        result: list[tuple[str, dict[str, Any]]] = []
        for item in items[:100]:
            if not isinstance(item, dict):
                continue
            preset = self._sanitize_custom("", item)
            result.append((self.new_preset_id(), preset))
        if not result:
            raise ValueError("文件中没有可用的预设")
        return result

    # ---------- 工具 ----------
    @staticmethod
    def new_preset_id() -> str:
        return "custom_" + uuid.uuid4().hex[:10]
