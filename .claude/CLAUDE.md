# CLAUDE.md

此文件为 Claude Code（claude.ai/code）在本仓库中工作时提供指导。

## 项目概述

基于 Claude Code 技能的图像处理工具集，提供背景移除（深度学习和传统算法）、AI 图片生成和游戏界面分析功能。提供 Gradio Web UI 和 CLI 两种使用方式。

## 快速开始（Web UI）

```bash
python main.py
```

零依赖启动（仅需 Python ≥ 3.10），自动打开浏览器进入环境初始化向导。首次使用按提示一键安装依赖和下载模型，之后直接进入功能界面。

## 虚拟环境

```bash
source .venv/bin/activate          # macOS/Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发用（pytest）
```

Python ≥ 3.10。运行依赖包括 torch、torchvision、transformers、safetensors、pillow、numpy、timm、kornia、google-genai、requests、scipy、gradio、modelscope。

## 测试

```bash
pytest tests/ -v
```
覆盖 `core/` 全部纯逻辑模块（config / api_keys / errors / skills / state / history），无需 GPU 或 API Key。

## 目录结构

```
.claude/skills/           # Claude Code 技能定义与脚本
  rmbg/                   # BiRefNet 深度学习去背景
  gen-image/              # 图片生成（Gemini / Wan2.7 Pro）
  bwdiff/                 # 黑白差分去背景
  bwgen/                  # 黑白背景图生成（bwdiff 前序，Gemini / Wan2.7 Pro）
  game-ui-analyzer/       # 游戏截图 UI 分析（纯 prompt，无脚本）
local/
  input/                  # 原始图片
    rmbg/                 # 按功能分类
    bwdiff/
  output/                 # 生成/处理后的图片
    rmbg/
    bwdiff/
    bwgen/
    gen-image/
  models/RMBG-2.0/        # BiRefNet 模型文件（model.safetensors、配置、onnx 变体）
  config.json             # UI 设置持久化（API Key、模型路径），gitignored
core/                     # 纯逻辑模块（无 Gradio 依赖）
  config.py               # 配置文件读写 + DEFAULTS
  api_keys.py             # API Key 解析 + use_api_key 上下文管理器
  errors.py               # 异常 → 中文友好文案
  skills.py               # skill 脚本懒加载 + 缓存
  state.py                # ModelRegistry 全局模型单例（线程安全）
  history.py              # 历史 JSON 读写 + 缩略图
tests/                    # pytest 单元测试
  conftest.py             # 共享 fixture
  test_*.py               # 每个 core 模块对应一个测试文件
main.py                   # 零依赖启动引导器（环境检测 + 初始化向导 + 反向代理）
app.py                    # Gradio Web UI（6 个功能 Tab）
requirements.txt          # 运行时依赖
requirements-dev.txt      # 开发依赖（pytest）
docs/superpowers/         # 设计与实施计划文档
```

## 技能脚本

所有脚本从项目根目录执行。

**去背景（深度学习，BiRefNet）：**
```bash
python .claude/skills/rmbg/scripts/rmbg_process.py -i <输入图片> -m local/models/RMBG-2.0 [-o <输出路径>]
```
CUDA 可用时自动使用 GPU，否则回退 CPU。输出 RGBA 透明 PNG。模型内部以 1024×1024 推理，mask 自动缩放回原图尺寸。

**去背景（黑白差分，无需模型）：**
```bash
python .claude/skills/bwdiff/scripts/bw_diff.py -b <黑底图> -w <白底图> [-o <输出路径>]
```
无需 GPU，仅依赖 pillow + numpy。要求两张图同机位、同光照、同分辨率，仅背景颜色不同。通过逐像素差值反算 alpha 通道。

**黑白背景图生成（Gemini / Wan2.7 Pro，bwdiff 前序）：**
```bash
# Gemini（默认）
python .claude/skills/bwgen/scripts/bw_gen.py -p "<主体描述>" [-r 16:9] [-s 2K]
# Wan2.7 Pro
python .claude/skills/bwgen/scripts/bw_gen.py -m wan -p "<主体描述>" [-r 16:9] [-s 2K]
```
从文字描述生成黑白双图，可直接传入 bwdiff 抠图。两步调用：先文生图生成黑底图，再图编辑换成白底。输出 `_black.png` 和 `_white.png`。

**图片生成（Gemini / Wan2.7 Pro）：**
```bash
# Gemini（默认）
python .claude/skills/gen-image/scripts/gen_image.py -p "<英文提示词>" [-r 16:9] [-s 2K]
# Wan2.7 Pro
python .claude/skills/gen-image/scripts/gen_image.py -m wan -p "<英文提示词>" [-r 16:9] [-s 2K]
```
Gemini 模型 `gemini-2.5-flash-image`，Wan2.7 模型 `wan2.7-image-pro`。支持宽高比：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`、`4:5`、`5:4`、`21:9`。分辨率：`512`（仅 Gemini）、`1K`、`2K`、`4K`（4K 仅文生图）。输出至 `local/output/`。

API 密钥可通过以下方式配置（优先级从高到低）：
- Web UI 设置页填写并保存到 `local/config.json`
- 环境变量 `GEMINI_API_KEY` / `DASHSCOPE_API_KEY`

CLI 模式下也优先读取 `local/config.json`，不存在时回退到环境变量。

## 模型

BiRefNet（RMBG-2.0）存放于 `local/models/RMBG-2.0/`。该目录下必须包含 `BiRefNet_config.py`、`birefnet.py` 和 `model.safetensors`，rmbg 脚本才能正常运行。

下载命令：`pip install modelscope && modelscope download --model AI-ModelScope/RMBG-2.0 --local_dir local/models/RMBG-2.0`

## 参考文档

改 Gradio UI 之前先看 `.claude/gradio-notes.md`——Gradio 6 主题/布局/CSS/事件 API 速查 + 本项目踩过的坑（重要：不要从零自拼 sidebar 布局，优先调主题）。
