"""声明式参数定义与命令行生成。

新增参数只需在 SPECS 中加一行，界面会自动生成对应控件。
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParamSpec:
    key: str
    flag: str
    label: str
    kind: str  # int | float | str | choice | path | flag
    default: Any
    group: str
    tip: str = ""
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    placeholder: str = ""


GROUPS = (
    ("basic", "通用"),
    ("performance", "性能"),
    ("sampling", "采样"),
    ("server", "服务"),
    ("advanced", "高级"),
)


SPECS: tuple[ParamSpec, ...] = (
    # ---------------- 通用 ----------------
    ParamSpec("alias", "--alias", "模型别名", "str", "", "basic",
              "在 /v1/models 中显示的模型名称，不影响实际加载。"),
    ParamSpec("ctx_size", "-c", "上下文长度 (tokens)", "int", 8192, "basic",
              "KV 缓存的总 token 数。越大越吃显存 / 内存，0 表示使用模型默认值。",
              minimum=0, maximum=1048576, placeholder="8192"),
    ParamSpec("n_predict", "-n", "最大生成 tokens", "int", -1, "basic",
              "单次请求最多生成的 token 数，-1 表示不限制。",
              minimum=-1, maximum=1048576, placeholder="-1"),
    ParamSpec("parallel", "-np", "并行槽位数", "int", 1, "basic",
              "同时处理的请求数，会平分上下文长度。",
              minimum=1, maximum=256, placeholder="1"),
    ParamSpec("jinja", "--jinja", "启用 Jinja 模板", "flag", False, "basic",
              "使用模型自带的 chat template 处理提示词（函数调用需要）。"),

    # ---------------- 性能 ----------------
    ParamSpec("n_gpu_layers", "-ngl", "GPU 卸载层数", "int", 99, "performance",
              "卸载到 GPU 的层数。0 = 纯 CPU；99 = 尽可能全部卸载。",
              minimum=0, maximum=9999, placeholder="99"),
    ParamSpec("threads", "-t", "CPU 线程数", "int", 0, "performance",
              "生成阶段线程数，0 = 自动检测。",
              minimum=0, maximum=256, placeholder="自动"),
    ParamSpec("threads_batch", "-tb", "批处理线程数", "int", 0, "performance",
              "prompt 处理阶段线程数，0 = 与生成线程相同。",
              minimum=0, maximum=256, placeholder="自动"),
    ParamSpec("n_cpu_moe", "--n-cpu-moe", "MoE CPU 层数", "int", 0, "performance",
              "MoE 模型中保留在 CPU 的专家层数，0 = 全部交给 GPU。",
              minimum=0, maximum=9999, placeholder="0"),
    ParamSpec("batch_size", "-b", "批处理大小", "int", 512, "performance",
              "prompt 批处理 token 数。",
              minimum=1, maximum=262144, placeholder="512"),
    ParamSpec("ubatch_size", "-ub", "微批处理大小", "int", 512, "performance",
              "更小粒度的批处理，影响峰值显存占用。",
              minimum=1, maximum=262144, placeholder="512"),
    ParamSpec("flash_attn", "-fa", "Flash Attention", "choice", "", "performance",
              "开启可显著降低长上下文显存占用；auto 由后端自行决定。",
              choices=("", "on", "off", "auto")),
    ParamSpec("cache_type_k", "--cache-type-k", "K 缓存量化", "choice", "", "performance",
              "KV 缓存 Key 的精度，q8_0 / q4_0 可省显存。",
              choices=("", "f16", "q8_0", "q4_0")),
    ParamSpec("cache_type_v", "--cache-type-v", "V 缓存量化", "choice", "", "performance",
              "KV 缓存 Value 的精度。",
              choices=("", "f16", "q8_0", "q4_0")),

    # ---------------- 采样 ----------------
    ParamSpec("temp", "--temp", "温度 temperature", "float", 0.8, "sampling",
              "越高越随机，0 为确定性输出。",
              minimum=0.0, maximum=2.0, placeholder="0.8"),
    ParamSpec("top_p", "--top-p", "Top-p", "float", 0.95, "sampling",
              "核采样阈值。", minimum=0.0, maximum=1.0, placeholder="0.95"),
    ParamSpec("top_k", "--top-k", "Top-k", "int", 40, "sampling",
              "每步只从概率最高的 k 个 token 中采样，0 = 不限制。",
              minimum=0, maximum=100000, placeholder="40"),
    ParamSpec("min_p", "--min-p", "Min-p", "float", 0.0, "sampling",
              "相对最大概率的最小阈值。", minimum=0.0, maximum=1.0, placeholder="0.0"),
    ParamSpec("repeat_penalty", "--repeat-penalty", "重复惩罚", "float", 1.1, "sampling",
              "大于 1 会抑制重复内容。", minimum=0.0, maximum=3.0, placeholder="1.1"),
    ParamSpec("repeat_last_n", "--repeat-last-n", "惩罚回溯长度", "int", 64, "sampling",
              "检查最近多少个 token 的重复，0 = 关闭。",
              minimum=0, maximum=1048576, placeholder="64"),
    ParamSpec("seed", "--seed", "随机种子", "int", -1, "sampling",
              "-1 = 每次随机。", minimum=-1, maximum=2147483647, placeholder="-1"),

    # ---------------- 服务 ----------------
    ParamSpec("host", "--host", "监听地址", "str", "127.0.0.1", "server",
              "127.0.0.1 仅本机可访问；0.0.0.0 允许局域网访问。\n"
              "对外开放务必同时设置 API Key 并使用反向代理。",
              placeholder="127.0.0.1"),
    ParamSpec("port", "--port", "端口", "int", 8080, "server",
              "HTTP API / WebUI 端口。", minimum=1, maximum=65535, placeholder="8080"),
    ParamSpec("api_key", "--api-key", "API Key", "str", "", "server",
              "设置后，客户端需在请求头携带 Authorization: Bearer <key>。\n"
              "注意：密钥会以明文保存在本地配置与预设文件中。"),
    ParamSpec("no_webui", "--no-webui", "禁用 WebUI", "flag", False, "server",
              "只保留 HTTP API，不启动内置网页界面。"),

    # ---------------- 高级 ----------------
    ParamSpec("mmproj", "--mmproj", "多模态投影模型", "path", "", "advanced",
              "视觉 / 音频模型的 mmproj GGUF 文件路径。"),
    ParamSpec("rope_scaling", "--rope-scaling", "RoPE 外推方式", "choice", "", "advanced",
              "长上下文外推：linear / yaarn。",
              choices=("", "none", "linear", "yaarn")),
    ParamSpec("rope_scale", "--rope-scale", "RoPE 缩放系数", "float", 0.0, "advanced",
              "配合 linear 使用。", minimum=0.0, maximum=1000.0, placeholder="0.0"),
    ParamSpec("rope_freq_base", "--rope-freq-base", "RoPE 频率基数", "float", 0.0, "advanced",
              "0 = 使用模型默认值。", minimum=0.0, maximum=1e12, placeholder="0.0"),
    ParamSpec("rope_freq_scale", "--rope-freq-scale", "RoPE 频率缩放", "float", 0.0, "advanced",
              "0 = 使用模型默认值。", minimum=0.0, maximum=1000.0, placeholder="0.0"),
    ParamSpec("log_file", "--log-file", "日志文件", "path", "", "advanced",
              "同时把日志写入该文件。"),
    ParamSpec("verbose", "-v", "详细日志", "flag", False, "advanced",
              "输出更多调试信息。"),
    ParamSpec("color", "-co", "彩色日志", "flag", False, "advanced",
              "在终端日志中使用 ANSI 颜色。"),
)

SPEC_BY_KEY = {spec.key: spec for spec in SPECS}


def default_values() -> dict[str, Any]:
    """返回一份全新的默认参数值。enable 键用于标记是否把该参数加入命令行。"""
    values: dict[str, Any] = {}
    for spec in SPECS:
        values[spec.key] = spec.default
        values[f"{spec.key}__enabled"] = spec.key in {
            "ctx_size", "n_predict", "parallel", "n_gpu_layers",
            "threads", "threads_batch", "batch_size", "ubatch_size",
            "temp", "top_p", "top_k", "repeat_penalty", "repeat_last_n",
            "seed", "host", "port",
        }
    return values


def coerce(spec: ParamSpec, value: Any) -> Any:
    """把任意来源的值安全转换为参数声明的类型，损坏数据回退到默认值。"""
    try:
        if spec.kind == "int":
            result = int(value)
        elif spec.kind == "float":
            result = float(value)
        elif spec.kind == "flag":
            return bool(value)
        elif spec.kind == "choice":
            text = "" if value is None else str(value)
            return text if text in spec.choices else spec.default
        else:
            return "" if value is None else str(value).strip()
        if spec.minimum is not None:
            result = max(result, spec.minimum)
        if spec.maximum is not None:
            result = min(result, spec.maximum)
        return int(result) if spec.kind == "int" else float(result)
    except (TypeError, ValueError, OverflowError):
        return spec.default


def normalize_values(raw: dict[str, Any] | None) -> dict[str, Any]:
    """合并存档值与默认值，对损坏/旧版本数据做类型校验与回退。"""
    values = default_values()
    if not isinstance(raw, dict):
        return values
    for spec in SPECS:
        if spec.key in raw:
            values[spec.key] = coerce(spec, raw[spec.key])
        enable_key = f"{spec.key}__enabled"
        if enable_key in raw:
            values[enable_key] = bool(raw[enable_key])
    return values


def _format_number(value: Any) -> str:
    """避免使用科学计数法，部分 llama.cpp 版本不解析 1e+12 这类写法。"""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.12f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def parse_extra_args(extra: str) -> tuple[list[str], str]:
    """解析额外参数，返回 (参数列表, 错误信息)。"""
    if not extra or not extra.strip():
        return [], ""
    try:
        return shlex.split(extra, posix=(os.name != "nt")), ""
    except ValueError as error:
        return [], f"额外参数引号未闭合：{error}"


def build_command(binary: str, model: str, values: dict[str, Any], extra_args: str = "") -> list[str]:
    """根据界面参数生成 argv。model 单独处理，保证始终位于 -m 之后。"""
    command = [binary.strip()]
    if model.strip():
        command.extend(["-m", model.strip()])

    for spec in SPECS:
        if not values.get(f"{spec.key}__enabled", False):
            continue
        value = coerce(spec, values.get(spec.key, spec.default))

        if spec.kind == "flag":
            if value:
                command.append(spec.flag)
            continue

        if isinstance(value, str) and not value:
            continue
        if value is None:
            continue
        command.extend([spec.flag, _format_number(value)])

    extra, _error = parse_extra_args(extra_args)
    command.extend(extra)
    return command


def shell_join(command: list[str]) -> str:
    """生成便于复制粘贴的命令字符串。"""
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)
