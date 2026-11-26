# llama.cpp Launcher

一个用 Python + PySide6 编写的跨平台 llama.cpp 图形启动器：选择模型和 `llama-server` 可执行文件，勾选参数即可启动本地 OpenAI 兼容 API 服务。

## 功能

- **跨平台**：macOS / Windows / Linux 同一套代码，自动查找 `llama-server`。
- **现代界面**：渐变应用栏、卡片布局、五组参数标签页、实时命令预览、可拖动侧栏。
- **深色模式**：跟随系统 / 浅色 / 深色三档切换，切换后已有日志会重新着色。
- **参数预设**：5 个内置预设（均衡、低显存、高性能 GPU、长上下文、API 服务），支持另存、覆盖、删除以及 **JSON 导入 / 导出**。
- **自定义启动参数**：每个参数都有开关，未启用的行会置灰；支持按名称 / 说明 / 命令行标志搜索、仅看已启用、一键恢复默认；另有「额外参数」输入框可追加任意 flag，并带引号语法校验。
- **启动前校验**：GGUF 文件头魔数校验、端口占用预检、模型与可执行文件有效性检查。
- **运行管理**：一键启动/停止、带时间戳的分级彩色日志、运行计时、WebUI 快捷入口、`/health` 健康检查、复制启动命令。
- **稳定性**：单实例保护、窗口模式下的全局异常捕获（`crash.log`）、退出前同步停止子进程、损坏配置自动回退。
- **配置持久化**：窗口位置、主题、路径、参数与预设保存在各平台标准配置目录。

## Windows 免安装版（推荐）

直接从 [GitHub Releases](https://github.com/fengshengzhu/llama-launcher/releases/latest) 下载 `LlamaLauncher.exe`，双击即可运行，无需安装 Python。把 `llama-server.exe` 放在 exe 同目录或 `bin/` 下会被自动检测，模型文件在界面中选择。

源码运行方式见下一节。

## 安装与运行（源码）

```bash
cd llama-launcher
python -m pip install -r requirements.txt
python main.py
```

要求 Python 3.10+。首次启动会自动创建配置文件，不会联网。

## 准备 llama-server

启动器本身不包含 llama.cpp 二进制。请自行从 [llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases) 下载或编译，然后任选一种方式让启动器找到它：

1. 在界面中点击「浏览」手动选择 `llama-server`（Windows 为 `llama-server.exe`）；
2. 放到项目目录的 `bin/` 下，或项目根目录；
3. 放到系统 `PATH`；
4. 设置环境变量 `LLAMA_SERVER_PATH` 指向可执行文件。

 macOS / Linux 下请确保文件有执行权限：`chmod +x llama-server`。

模型使用 `.gguf` 文件，在「模型文件」一行点击「浏览」选择即可。

## 参数与预设

- 参数定义在 `llama_launcher/params.py` 的 `SPECS` 中，新增一行即可自动生成界面控件并参与命令构建。
- `参数xxx__enabled` 控制该参数是否进入命令行；`flag` 类型直接用复选框表示启用。
- 「额外参数」使用 shell 风格解析：Linux/macOS 支持引号，Windows 下带空格的路径也请用引号包裹；引号未闭合会在界面提示并阻止启动。
- `-fa on|off|auto`（Flash Attention 带值写法）需要较新版本的 llama.cpp；旧版本只支持 `-fa` 作为开关，可在「额外参数」里直接写 `-fa`。
- API Key 会以明文保存在本地配置与预设文件中，请勿在其中填写复用的重要密钥。
- 预设保存在配置目录的 `presets.json`，设置在 `settings.json`：
  - Windows：`%APPDATA%\LlamaLauncher`
  - macOS：`~/Library/Application Support/LlamaLauncher`
  - Linux：`~/.config/llama-launcher`（或 `$XDG_CONFIG_HOME/llama-launcher`）

## 目录结构

```
llama-launcher/
├── main.py                     # 入口（含单实例、异常钩子、--self-test）
├── requirements.txt
├── build.bat                   # 一键打包 exe
├── assets/                     # 图标与生成脚本
├── tests/smoke_test.py         # 回归测试
├── llama_launcher/
│   ├── params.py               # 参数 schema、类型校验、命令生成
│   ├── config.py               # 配置与预设持久化、导入导出
│   ├── platform_utils.py       # 路径查找、GGUF 校验、端口探测
│   ├── runner.py               # QProcess 进程管理与健康检查
│   ├── theme.py                # 深浅色主题与样式表
│   └── ui/
│       ├── common.py
│       ├── param_panel.py      # 参数面板（搜索 / 启用态 / 重置）
│       ├── preset_panel.py     # 预设面板（徽章 / 导入导出）
│       └── main_window.py      # 主窗口
```

回归测试：`python tests/smoke_test.py`，输出 `SMOKE_TEST_OK` 即通过。

## 打包为 Windows exe

双击 `build.bat`，或直接运行：

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name LlamaLauncher ^
  --icon assets/app_icon.ico --distpath dist --workpath build --specpath . main.py
```

产物为 `dist/LlamaLauncher.exe`（单文件，约 45 MB，已内置 Python 与 Qt 运行时，无需目标机器安装 Python）。

验证打包结果：

```bash
set LLAMA_LAUNCHER_SELFTEST_FILE=%TEMP%\launcher-selftest.json
dist\LlamaLauncher.exe --self-test
type %LLAMA_LAUNCHER_SELFTEST_FILE%
```

看到 `{"ok": true, ...}` 即表示 exe 内界面可正常创建。图标可用 `python assets/make_icon.py` 重新生成（需 Pillow）。

把 `llama-server.exe` 放在 exe 同目录或 `bin/` 下即可被自动检测；模型文件仍通过界面选择。单文件模式每次启动需解压到临时目录，首次打开约 1–2 秒属正常现象。

## 已知限制

- 单文件 exe 每次运行会在临时目录解压；若本机安全软件拦截 PyInstaller 打包程序，需添加信任。
- 窗口模式没有控制台，未处理异常会写入配置目录的 `crash.log` 并弹窗提示。
- 端口预检与实际绑定之间存在极小竞态，若服务仍报地址占用，请更换端口后重试。
- 健康检查使用 `/health` 端点，极旧版本的 llama.cpp 可能不提供该端点。
- 深色 / 浅色主题切换后，Qt 原生文件对话框仍使用系统外观。
