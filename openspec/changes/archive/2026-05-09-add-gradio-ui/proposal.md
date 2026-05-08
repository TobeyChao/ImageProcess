## Why

当前所有图片处理功能通过命令行脚本或 Claude Code Skill 工具调用，参数靠文字描述容易出错，多步骤管线（bwgen→bwdiff）需要手动串联，环境初始化涉及多个独立步骤（创建 venv、装依赖、下载模型、配 API Key），对用户不友好。需要一个本地 Web UI 统一管理参数、环境、执行和预览。

## What Changes

- 新增 `main.py`（零依赖启动脚本，纯 Python 标准库），自动检测环境并引导初始化
- 新增 Gradio Web UI（`app.py`），提供参数可视化配置、原图/结果对比预览、一键管线
- 新增 `requirements.txt` 声明所有 Python 依赖
- 重构四个处理脚本（rmbg、bwdiff、bwgen、gen-image），将核心逻辑抽成可复用函数，CLI 保持为薄壳
- 模型下载渠道从 HuggingFace 切换到 ModelScope（`AI-ModelScope/RMBG-2.0`）
- API Key 配置从环境变量迁移到 UI 设置页持久化（`local/config.json`）
- 新增 `local/` 目录下的 `.gitignore` 规则确保 config.json 不入库
- 更新 CLAUDE.md 和 rmbg setup.md 中的下载命令和依赖说明

## Capabilities

### New Capabilities

- `web-ui`: Gradio Web UI，包含环境初始化向导、五个功能 Tab（去背景、黑白差分、生黑白底图、生图、一键管线）、设置页（模型路径 + API Key 管理），所有步骤实时日志/进度反馈
- `script-refactor`: 四个处理脚本的函数化重构，核心逻辑与 CLI 界面分离，可被 Gradio UI 直接 import 调用

### Modified Capabilities

- `bwgen`: API Key 获取方式从纯环境变量扩展为 UI 配置优先（`local/config.json` > 环境变量）

## Impact

- 新增文件：`main.py`、`app.py`、`requirements.txt`、`local/config.json`（首次运行时创建）
- 修改文件：`.claude/skills/rmbg/scripts/rmbg_process.py`、`bwdiff/scripts/bw_diff.py`、`bwgen/scripts/bw_gen.py`、`gen-image/scripts/gen_image.py`（重构为函数化）
- 文档更新：`.claude/CLAUDE.md`、`.claude/skills/rmbg/references/setup.md`
- 新增依赖：`gradio`、`modelscope`
- 向后兼容：CLI 接口参数不变，现有 Skill 调用方式不受影响
