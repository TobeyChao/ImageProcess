# ImageProcess

本地图像处理工具箱，基于 Claude Code 技能构建。提供深度学习和传统算法两种背景移除方式、AI 图片生成、游戏 UI 分析，全程通过浏览器界面操作，无需编写代码。

English → [README.md](README.md)

## 功能

- **去背景（BiRefNet）** — 深度学习模型，适合复杂自然背景，输出带透明通道的 PNG
- **黑白差分** — 通过黑底/白底双图数学反算 alpha 通道，无需模型，精度极高
- **色键抠图** — 泛洪填充移除纯色背景，效果等同 Photoshop 魔术橡皮擦
- **图片生成** — 通过 Gemini 或阿里云万象 Wan2.7 Pro 文生图
- **生黑白底图** — 为黑白差分流程生成双图素材（黑底 + 白底）
- **一键管线** — 生黑白底图 → 黑白差分一键串联
- **设置** — 持久化保存 API Key 和模型路径

## 快速开始

### 方式一 — 双击启动（无需打开终端）

| 系统 | 文件 |
|------|------|
| Windows | 双击 `setup.bat` |
| macOS | 双击 `setup.command`（首次需在「安全性与隐私」允许） |

需提前安装 Python 3.10+。启动脚本调用 `python main.py`，首次运行会打开浏览器并进入环境初始化向导，按提示一键安装依赖和下载模型。

### 方式二 — 命令行

```bash
python main.py
```

### 方式三 — 手动虚拟环境

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

## GPU 加速

| 平台 | 加速方式 | 前提条件 |
|------|---------|---------|
| NVIDIA | CUDA | PyTorch CUDA 版本 |
| AMD（Windows） | ROCm | Python 3.12，ROCm PyTorch 包 |
| Apple Silicon | MPS | macOS 12.3+，M1/M2/M3 芯片 |
| 任意平台 | CPU | 自动回退，无需配置 |

启动向导自动检测 GPU；若检测到 NVIDIA 但缺少 CUDA torch，会提供一键安装入口。Apple Silicon 用户 MPS 加速由 PyTorch 自动启用，向导无需额外操作。

## 功能 Tab 一览

| Tab | 功能 | 依赖 | 需 API Key |
|-----|------|------|-----------|
| ⚙ 设置 | 保存 API Key 和模型路径 | — | — |
| 🎯 去背景 | BiRefNet 深度学习抠图 | BiRefNet 模型（840 MB） | — |
| ⬛⬜ 黑白差分 | 双图数学反算 alpha 通道 | pillow、numpy | — |
| 🌈 色键抠图 | 泛洪填充移除纯色背景 | pillow、numpy | — |
| 🎨 生黑白底图 | 从文字描述生成黑白双图 | Gemini 或 Wan2.7 API | ✓ |
| 📷 生图 | 文生图 | Gemini 或 Wan2.7 API | ✓ |
| 🔄 一键管线 | 生黑白底图 → 黑白差分串联 | Gemini 或 Wan2.7 API | ✓ |

## CLI 用法

所有脚本从项目根目录执行。

**去背景（BiRefNet）：**

```bash
python .claude/skills/rmbg/scripts/rmbg_process.py \
  -i <输入图片> -m local/models/RMBG-2.0 [-o <输出路径>] [-t 0.5]
```

CUDA / ROCm / MPS 可用时自动 GPU 加速，否则回退 CPU。输出 RGBA 透明 PNG。

**黑白差分：**

```bash
python .claude/skills/bwdiff/scripts/bw_diff.py \
  -b <黑底图> -w <白底图> [-o <输出路径>]
```

两张图需同机位、同光照、同分辨率，仅背景颜色不同。

**色键抠图：**

```bash
python .claude/skills/chroma-key/scripts/chroma_key.py \
  -i <输入图片> [-c "#FFFFFF"] [-t 32] [-o <输出路径>]
```

不传 `-c` 或传入 `auto` 时自动检测背景色（四角采样中位数）；`-t` 为容差，默认 32。

**生黑白底图：**

```bash
# Gemini（默认）
python .claude/skills/bwgen/scripts/bw_gen.py -p "<主体描述>" [-r 16:9] [-s 2K]
# Wan2.7 Pro
python .claude/skills/bwgen/scripts/bw_gen.py -m wan -p "<主体描述>"
```

输出 `_black.png` 和 `_white.png`，可直接传入黑白差分脚本。

**图片生成：**

```bash
# Gemini（默认）
python .claude/skills/gen-image/scripts/gen_image.py -p "<英文提示词>" [-r 16:9] [-s 2K]
# Wan2.7 Pro
python .claude/skills/gen-image/scripts/gen_image.py -m wan -p "<英文提示词>"
```

支持宽高比：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`、`4:5`、`5:4`、`21:9`。分辨率：`1K`、`2K`、`4K`（Wan2.7 不支持 `512`）。

## API Key 配置

两种方式：

1. **Web UI（推荐）**：在 ⚙ 设置 Tab 填写后自动保存至 `local/config.json`（已 gitignore）。
2. **环境变量**：设置 `GEMINI_API_KEY` 和/或 `DASHSCOPE_API_KEY`，Web UI 读取作为回退。

`local/config.json` 优先级高于环境变量。

---

## 架构

```
core/                     # 纯逻辑模块（无 Gradio/UI 依赖，可独立测试）
  config.py               # 配置文件读写 + 原子保存（os.replace）+ env-var 回退
  api_keys.py             # 统一 API Key 解析 + use_api_key() 上下文管理器
  errors.py               # 异常 → 中文友好文案（模式匹配优先）
  skills.py               # 技能脚本懒加载 + 缓存
  state.py                # ModelRegistry 全局模型单例（线程安全，per-key 锁）
  history.py              # HistoryStore 持久化操作历史 + 缩略图生成
app.py                    # Gradio Web UI（7 个功能 Tab）
main.py                   # 零依赖启动引导器（环境检测 + 初始化向导 + 反向代理）
setup.bat                 # Windows 一键启动脚本（双击运行）
setup.command             # macOS 一键启动脚本（双击运行）
.claude/skills/           # Claude Code 技能定义与脚本
  rmbg/                   # BiRefNet 深度学习去背景
  bwdiff/                 # 黑白差分去背景
  bwgen/                  # 黑白背景图生成（bwdiff 前序）
  chroma-key/             # 色键抠图（泛洪填充 + 容差 + 边缘柔化）
  gen-image/              # 图片生成
  game-ui-analyzer/       # 游戏截图 UI 分析（纯 prompt，无脚本）
local/
  output/                 # 生成/处理后的图片（按功能分子目录）
  models/RMBG-2.0/        # BiRefNet 模型文件（model.safetensors、配置等）
  config.json             # UI 设置持久化（API Key、模型路径），gitignored
tests/                    # pytest 单元测试（每个 core 模块一个 test_*.py）
```

**关键设计约定：**

- `core/` 不依赖 Gradio，所有纯逻辑在此实现，`app.py` 只做 UI 胶水。
- 840 MB BiRefNet 模型通过 `state.registry.get_or_load()` 跨会话共享，per-key 锁防并发初次加载竞态。
- `api_keys.use_api_key(config_path, model)` 上下文管理器统一 Key 解析与清理，替代各 Tab 中重复的 key 检查逻辑。

## Core 模块

| 文件 | 职责 |
|------|------|
| `core/config.py` | 读写 `local/config.json`，原子保存 |
| `core/api_keys.py` | 从配置文件或环境变量解析 API Key |
| `core/errors.py` | 异常转中文友好文案 |
| `core/skills.py` | 懒加载并缓存技能脚本 |
| `core/state.py` | 线程安全模型单例注册表 |
| `core/history.py` | 持久化操作历史，生成缩略图 |

## 添加新技能 / Tab

1. 创建 `.claude/skills/<name>/SKILL.md` — Claude Code 技能定义（触发条件、参数、执行步骤）
2. 编写 `.claude/skills/<name>/scripts/<name>.py` — 处理脚本，从项目根目录执行
3. 在 `app.py` 中添加 `with gr.Tab("名称"):` 块，遵循现有 Tab 的布局模式
4. 在 `core/skills.py` 中注册技能加载器条目
5. 在 `tests/test_skills.py` 中添加测试，验证技能正确加载

## 测试

```bash
pytest tests/ -v
```

覆盖所有 `core/` 纯逻辑模块，无需 GPU 或 API Key，秒级完成。

## 模型下载

BiRefNet（RMBG-2.0）需放置于 `local/models/RMBG-2.0/`，必须包含 `BiRefNet_config.py`、`birefnet.py`、`model.safetensors`。

```bash
pip install modelscope
modelscope download --model AI-ModelScope/RMBG-2.0 --local_dir local/models/RMBG-2.0
```
