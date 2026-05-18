## Context

`main.py` 目前是一个 ~600 行的零依赖引导器，包含：
- HTTP 服务器（`SSEHandler`）—— 服务初始化 HTML 页面 + SSE 事件流
- 反向代理（`ReverseProxyHandler`）—— 转发 7860 → 7861
- 内联 HTML（`SETUP_HTML`）—— 完整的浏览器 setup 页面
- 端口检测 + 冲突处理

初始化完成后，Gradio 跑在 7861，浏览器通过 7860 的反代访问。这套架构引入了端口协调问题，且为"浏览器可视化向导"付出了巨大代码成本。

目标：将初始化流程从浏览器搬回终端，移除 HTTP/SSE/Proxy 三层，让 `main.py` 回归本质——检测环境 + 交互确认 + 启动应用。

## Goals / Non-Goals

**Goals:**
- 初始化向导完全在终端 CLI 执行，无浏览器依赖
- 必装步骤（venv、deps、model）逐个确认，可选步骤（GPU torch）默认跳过
- 环境就绪时零交互直接启动 Gradio
- 删除所有 HTTP/SSE/Proxy/内联 HTML 代码
- `app.py` 用 Gradio 默认端口，不加 `server_port`

**Non-Goals:**
- 不改 Gradio UI 布局/功能
- 不改 setup.bat / setup.command
- 不增加新的 pip 依赖（main.py 保持零依赖）
- 不改 GPU 检测逻辑（只改其展示层）

## Decisions

### D1: 交互模式：逐步骤 Y/n 确认

```
必装项 (默认 Y):
  是否创建虚拟环境？[Y/n]
  是否安装依赖包？[Y/n]
  是否下载模型？[Y/n]

可选 (默认 N):
  是否安装 CUDA 版 PyTorch 启用 GPU 加速？[y/N]
```

必装项默认 Y（回车即确认），可选默认 N（回车即跳过）。GPU 信息提前展示，让用户做知情决策。

### D2: 环境就绪时零交互

`check_python()` → `check_venv()` → `check_deps()` → `check_model()` 全部 OK 时，直接打印检查结果并启动 Gradio，不询问任何问题。只在有缺失时才进入交互。

### D3: pip/model 输出直接流到终端

不再需要 SSE/EventQueue/log 回调。`subprocess.Popen` 的 stdout 直接 `print` 到终端（或 `sys.stdout.write`），错误也直接显示。这比之前的浏览器端日志更直观。

### D4: 可选 GPU 安装整合到主流程

GPU 检测结果在环境检查中展示，如果检测到可用 GPU（NVIDIA/AMD）但未启用 CUDA/ROCm，在必装步骤完成后提示可选安装。用户选 y 则执行安装命令，选 n 则跳过（后续可在 Gradio 设置 Tab 查看安装命令）。

### D5: 直接启动 Gradio（无反向代理）

`main.py` 执行 `subprocess.Popen([venv_python, "app.py"])` 后直接退出（或 wait），Gradio 独占默认端口 7860。不再需要 `_delayed_shutdown` / `run_proxy` / `wait_for_gradio` 等协调逻辑。

## Risks / Trade-offs

- [启动空窗期] `main.py` 退出后到 Gradio 就绪前有几秒空窗，浏览器在此期间不可用。→ 打印 "Gradio 启动中，稍候打开 http://127.0.0.1:7860"，`webbrowser.open()` 延迟 3 秒执行。
- [Windows 双击体验] setup.bat 双击后终端窗口会随 `main.py` 退出而关闭。当环境就绪直接启动 Gradio 时没问题（main.py 会 wait Gradio 进程）。当需要交互时，`input()` 会保持终端打开。但当所有步骤执行完（用户一路 y 到底），main.py 启动 Gradio 并退出后，终端窗口也会关闭——Gradio 进程需用 `CREATE_NEW_PROCESS_GROUP`（Windows）或直接 `Popen` 后 `wait()`（跨平台一致）。
- [setup.bat/setup.command] 不改，但需验证 Windows 下终端关闭时机是否合理。
