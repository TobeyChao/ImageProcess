# CLAUDE.md

此文件为 Claude Code（claude.ai/code）在本仓库中工作时提供指导。

## 项目概述

基于 Claude Code 技能的图像处理工具集，提供背景移除（深度学习和传统算法）、AI 图片生成和游戏界面分析功能。提供 Gradio Web UI 和 CLI 两种使用方式。

## 快速开始（Web UI）

```bash
python main.py
```

零依赖启动（仅需 Python ≥ 3.10；Windows AMD ROCm GPU 加速需 Python 3.12），自动打开浏览器进入环境初始化向导。首次使用按提示一键安装依赖和下载模型，之后直接进入功能界面。

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

## 架构

```
core/                     # 纯逻辑模块（无 Gradio/UI 依赖，可独立测试）
  config.py               # 配置文件读写 + 原子保存（os.replace）+ env-var 回退
  api_keys.py             # 统一 API Key 解析 + use_api_key() 上下文管理器
  errors.py               # 异常 → 中文友好文案（模式匹配优先）
  skills.py               # 技能脚本懒加载 + 缓存
  state.py                # ModelRegistry 全局模型单例（线程安全，per-key 锁）
  history.py              # HistoryStore 持久化操作历史 + 缩略图生成
app.py                    # Gradio Web UI（6 个功能 Tab）
main.py                   # 零依赖启动引导器（环境检测 + 初始化向导 + 反向代理）
.claude/skills/           # Claude Code 技能定义与脚本
  rmbg/                   # BiRefNet 深度学习去背景
  bwdiff/                 # 黑白差分去背景
  bwgen/                  # 黑白背景图生成（bwdiff 前序）
  gen-image/              # 图片生成
  game-ui-analyzer/       # 游戏截图 UI 分析（纯 prompt，无脚本）
local/
  output/                 # 生成/处理后的图片（按功能分子目录）
  models/RMBG-2.0/       # BiRefNet 模型文件（model.safetensors、配置、onnx 变体）
  config.json             # UI 设置持久化（API Key、模型路径），gitignored
tests/                    # pytest 单元测试（每个 core 模块一个 test_*.py）
```

### 关键设计约定

- **`core/` 不依赖 Gradio**，所有纯逻辑在此实现，`app.py` 只做 UI 胶水。
- **模型缓存放 `state.registry.get_or_load()`**——840MB BiRefNet 模型跨会话共享，避免重复加载。per-key 锁防止并发初次加载竞态。
- **API Key 用 `api_keys.use_api_key(config_path, model)`** 上下文管理器，替代各 Tab 中重复的 key 检查/设置逻辑。`MissingKey` 异常在 `errors.py` 中有对应中文文案。
- **错误处理**：`app.py` 中所有 try/except 都走 `errors.user_message(e)` 转中文友好文案后再返回给 UI。
- **`bwdiff_process(black, white)`** 直接接收两张 PIL 图作为参数，不再使用模块级全局变量缓存上传图（多标签页共享会冲突）。

## 技能脚本

所有脚本从项目根目录执行。

**去背景（深度学习，BiRefNet）：**
```bash
python .claude/skills/rmbg/scripts/rmbg_process.py -i <输入图片> -m local/models/RMBG-2.0 [-o <输出路径>]
```
CUDA / ROCm 可用时自动使用 GPU，否则回退 CPU。输出 RGBA 透明 PNG。模型内部以 1024×1024 推理，mask 自动缩放回原图尺寸。

**去背景（黑白差分，无需模型）：**
```bash
python .claude/skills/bwdiff/scripts/bw_diff.py -b <黑底图> -w <白底图> [-o <输出路径>]
```
无需 GPU，仅依赖 pillow + numpy。要求两张图同机位、同光照、同分辨率，仅背景颜色不同。核心函数 `compute_alpha(black_arr, white_arr)` 通过逐像素差值反算 alpha 通道；`bw_diff(black_path, white_path)` 封装文件 I/O 直接返回 RGBA PIL Image。

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

API 密钥通过 `api_keys.resolve()` 解析，优先级：`local/config.json` > 环境变量 `GEMINI_API_KEY` / `DASHSCOPE_API_KEY`。

## 模型

BiRefNet（RMBG-2.0）存放于 `local/models/RMBG-2.0/`。该目录下必须包含 `BiRefNet_config.py`、`birefnet.py` 和 `model.safetensors`，rmbg 脚本才能正常运行。

下载命令：`pip install modelscope && modelscope download --model AI-ModelScope/RMBG-2.0 --local_dir local/models/RMBG-2.0`

## 参考文档

改 Gradio UI 之前先看 `.claude/gradio-notes.md`——Gradio 6 主题/布局/CSS/事件 API 速查 + 本项目踩过的坑（重要：不要从零自拼 sidebar 布局，优先调主题）。
