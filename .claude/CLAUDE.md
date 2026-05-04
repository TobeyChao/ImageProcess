# CLAUDE.md

此文件为 Claude Code（claude.ai/code）在本仓库中工作时提供指导。

## 项目概述

基于 Claude Code 技能的图像处理工具集，提供背景移除（深度学习和传统算法）、AI 图片生成和游戏界面分析功能。

## 虚拟环境

```bash
source .venv/bin/activate
```

Python 3.14。依赖包括 torch、torchvision、transformers、safetensors、pillow、numpy、timm、kornia、google-genai。

## 目录结构

```
.claude/skills/           # Claude Code 技能定义与脚本
  rmbg/                   # BiRefNet 深度学习去背景
  gen-image/              # Gemini 图片生成
  bwdiff/                 # 黑白差分去背景
  game-ui-analyzer/       # 游戏截图 UI 分析（纯 prompt，无脚本）
local/
  input/                  # 原始图片
  output/                 # 生成/处理后的图片
  models/RMBG-2.0/        # BiRefNet 模型文件（model.safetensors、配置、onnx 变体）
docs/superpowers/         # 技能开发的计划与设计文档
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

**图片生成（Gemini API）：**
```bash
python .claude/skills/gen-image/scripts/gen_image.py -p "<英文提示词>" [-r 16:9] [-s 2K]
```
使用 Gemini 模型 `gemini-3.1-flash-image-preview`。支持宽高比：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`、`4:5`、`5:4`、`21:9`。分辨率：`512`、`1K`、`2K`、`4K`。输出至 `local/output/`。

API 密钥通过 `GEMINI_API_KEY` 环境变量传入，本地在 `.claude/settings.local.json` 中配置（已在 `.gitignore` 中排除）。

## 模型

BiRefNet（RMBG-2.0）存放于 `local/models/RMBG-2.0/`。该目录下必须包含 `BiRefNet_config.py`、`birefnet.py` 和 `model.safetensors`，rmbg 脚本才能正常运行。

下载命令：`huggingface-cli download briaai/RMBG-2.0 --local-dir local/models/RMBG-2.0`
