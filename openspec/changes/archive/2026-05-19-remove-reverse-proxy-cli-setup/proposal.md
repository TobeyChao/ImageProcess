## Why

当前 `main.py` 用 ~600 行 HTTP 服务器 + SSE + 内联 HTML + 反向代理实现浏览器端的初始化向导，复杂度高且端口协调容易出错。改为终端 CLI 交互后，init 和 run 的职责分离更清晰，代码大幅精简，且终端体验更适合开发者工具。

## What Changes

- **BREAKING**: 去掉反向代理架构，`main.py` 不再启动 HTTP 服务器
- 初始化向导从浏览器页面改为终端控制台交互式问答
- 必装项（venv、依赖、模型）逐步骤求确认后执行；可选（GPU torch）默认跳过，用户主动选才装
- 环境已就绪时直接启动 Gradio，零交互
- `app.py` 不再需要 `server_port`，全走默认端口
- 保留 `setup.bat` / `setup.command` 一键启动脚本（它们打开终端后自然进入控制台交互）

## Capabilities

### New Capabilities

- `cli-setup`: 终端控制台初始化流程——环境检查打印、必装/可选步骤区分、逐步 `input()` 确认、pip/model 输出实时流到终端

### Modified Capabilities

- `web-ui`: 去掉"HTTP 服务器 + SSE + 浏览器安装向导 + 反向代理"需求，改为"终端交互式初始化 + 直接启动 Gradio"

## Impact

- [main.py](../../../main.py): 删除约 600 行（EventQueue、SSEHandler、ReverseProxyHandler、SETUP_HTML、端口检测），新增约 50 行 CLI 交互
- [app.py](../../../app.py): 去掉 `server_port=7861` 参数（如有），用 Gradio 默认端口
- `setup.bat` / `setup.command`: 不变
