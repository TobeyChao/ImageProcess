# ImageProcess

A local image-processing toolbox built on Claude Code skills. Remove backgrounds with deep learning or algorithm-based methods, generate AI images, and analyze game UI — all from a browser interface with no coding required.

中文文档 → [README.zh-CN.md](README.zh-CN.md)

## Features

- **Background Removal (BiRefNet)** — deep-learning model, handles complex natural backgrounds, outputs transparent PNG
- **Black-White Diff** — mathematically extracts alpha channel from black/white background image pairs, no model needed, pixel-perfect
- **Chroma Key** — flood-fill removal of solid-color backgrounds, equivalent to Photoshop's Magic Eraser
- **Image Generation** — text-to-image via Gemini or Alibaba Wan2.7 Pro
- **BW Background Generation** — generate black/white image pairs from a text description (BW Diff prerequisite)
- **Pipeline** — chain BW generation → BW diff in one click
- **Settings** — persistent API key and model path configuration

## Quick Start

### Option 1 — Double-click launcher (no terminal needed)

| Platform | File |
|----------|------|
| Windows | Double-click `setup.bat` |
| macOS | Double-click `setup.command` (allow in Security & Privacy on first run) |

Requires Python 3.10+ to be installed. The launcher calls `python main.py`, which opens your browser and runs a first-time setup wizard that installs dependencies and downloads the model automatically.

### Option 2 — Command line

```bash
python main.py
```

### Option 3 — Manual virtual environment

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

## GPU Acceleration

| Platform | Backend | Requirement |
|----------|---------|-------------|
| NVIDIA | CUDA | PyTorch with CUDA build |
| AMD (Windows) | ROCm | Python 3.12, ROCm PyTorch build |
| Apple Silicon | MPS | macOS 12.3+, M1/M2/M3 chip |
| Any | CPU | automatic fallback, no setup needed |

The startup wizard detects your GPU and provides a one-click install for the matching PyTorch build when needed. Apple Silicon MPS acceleration is enabled automatically by PyTorch — no wizard step required.

## Tabs & Capabilities

| Tab | Description | Dependency | API Key |
|-----|-------------|------------|---------|
| ⚙ Settings | Save API keys & model path | — | — |
| 🎯 Background Removal | BiRefNet deep-learning removal | BiRefNet model (840 MB) | — |
| ⬛⬜ BW Diff | Alpha from black/white image pair | pillow, numpy | — |
| 🌈 Chroma Key | Flood-fill solid-color removal | pillow, numpy | — |
| 🎨 BW Background Gen | Generate black/white pairs from text | Gemini or Wan2.7 API | ✓ |
| 📷 Image Generation | Text-to-image | Gemini or Wan2.7 API | ✓ |
| 🔄 Pipeline | BW Gen → BW Diff in one click | Gemini or Wan2.7 API | ✓ |

## CLI Usage

All scripts run from the project root.

**Background Removal (BiRefNet):**

```bash
python .claude/skills/rmbg/scripts/rmbg_process.py \
  -i <input_image> -m local/models/RMBG-2.0 [-o <output>] [-t 0.5]
```

CUDA / ROCm / MPS accelerated when available, falls back to CPU. Outputs RGBA transparent PNG.

**BW Diff:**

```bash
python .claude/skills/bwdiff/scripts/bw_diff.py \
  -b <black_bg_image> -w <white_bg_image> [-o <output>]
```

Both images must share the same camera angle, lighting, and resolution — only the background color differs.

**Chroma Key:**

```bash
python .claude/skills/chroma-key/scripts/chroma_key.py \
  -i <input_image> [-c "#FFFFFF"] [-t 32] [-o <output>]
```

Omit `-c` or pass `auto` for auto-detection (corner pixel sampling). `-t` is the tolerance radius in RGB space (default 32).

**BW Background Generation:**

```bash
# Gemini (default)
python .claude/skills/bwgen/scripts/bw_gen.py -p "subject description" [-r 16:9] [-s 2K]
# Wan2.7 Pro
python .claude/skills/bwgen/scripts/bw_gen.py -m wan -p "subject description"
```

Outputs `_black.png` and `_white.png` ready for the BW Diff script.

**Image Generation:**

```bash
# Gemini (default)
python .claude/skills/gen-image/scripts/gen_image.py -p "prompt in English" [-r 16:9] [-s 2K]
# Wan2.7 Pro
python .claude/skills/gen-image/scripts/gen_image.py -m wan -p "prompt in English"
```

Supported aspect ratios: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `4:5`, `5:4`, `21:9`. Resolutions: `1K`, `2K`, `4K` (Wan2.7 does not support `512`).

## API Keys

Two ways to provide API keys:

1. **Web UI (recommended):** Open the ⚙ Settings tab and enter your keys. They are saved to `local/config.json` (gitignored).
2. **Environment variables:** Set `GEMINI_API_KEY` and/or `DASHSCOPE_API_KEY`. Used as fallback when `local/config.json` has no key.

`local/config.json` takes priority over environment variables.

---

## Architecture

```
core/                     # Pure-logic modules (no Gradio/UI dependency, testable standalone)
  config.py               # Config read/write + atomic save (os.replace) + env-var fallback
  api_keys.py             # Unified API key resolution + use_api_key() context manager
  errors.py               # Exception → user-friendly messages (pattern matching)
  skills.py               # Skill script lazy-loading + cache
  state.py                # ModelRegistry global singleton (thread-safe, per-key locks)
  history.py              # HistoryStore persistent operation history + thumbnail generation
app.py                    # Gradio Web UI (7 functional tabs)
main.py                   # Zero-dependency launcher (env detection + setup wizard + proxy)
setup.bat                 # Windows one-click launcher (double-click to run)
setup.command             # macOS one-click launcher (double-click to run)
.claude/skills/           # Claude Code skill definitions and scripts
  rmbg/                   # BiRefNet deep-learning background removal
  bwdiff/                 # Black-white diff background removal
  bwgen/                  # BW background generation (bwdiff prerequisite)
  chroma-key/             # Solid-color background removal (flood fill + tolerance)
  gen-image/              # Image generation
  game-ui-analyzer/       # Game screenshot UI analysis (prompt only, no script)
local/
  output/                 # Generated/processed images (per-feature subdirectories)
  models/RMBG-2.0/        # BiRefNet model files (model.safetensors + config)
  config.json             # UI settings persistence (API keys, model path) — gitignored
tests/                    # pytest unit tests (one test_*.py per core module)
```

**Key design decisions:**

- `core/` has no Gradio dependency — all logic lives here, `app.py` is pure UI glue.
- The 840 MB BiRefNet model is cached via `state.registry.get_or_load()` and shared across sessions. Per-key locks prevent concurrent first-load race conditions.
- `api_keys.use_api_key(config_path, model)` context manager centralises key resolution and cleanup, replacing per-tab boilerplate.
- Error handling: all `try/except` in `app.py` route through `errors.user_message(e)` which converts exceptions to user-friendly Chinese messages.

## Core Modules

| File | Responsibility |
|------|---------------|
| `core/config.py` | Read/write `local/config.json` with atomic saves (`os.replace`) |
| `core/api_keys.py` | Resolve API keys from config or env vars; `use_api_key()` context manager |
| `core/errors.py` | Convert exceptions to user-friendly messages via pattern matching |
| `core/skills.py` | Lazy-load and cache skill scripts |
| `core/state.py` | Thread-safe model singleton registry |
| `core/history.py` | Persist operation history and generate thumbnails |

## Adding a New Skill / Tab

1. Create `.claude/skills/<name>/SKILL.md` — skill definition for Claude Code (trigger conditions, parameters, execution steps)
2. Write `.claude/skills/<name>/scripts/<name>.py` — processing script, run from project root
3. Add a `with gr.Tab("Label"):` block in `app.py`, following the pattern of existing tabs
4. Register the skill loader entry in `core/skills.py`
5. Add a test in `tests/test_skills.py` to verify the skill loads correctly

## Tests

```bash
pytest tests/ -v
```

Covers all `core/` pure-logic modules. No GPU or API key required. Completes in seconds.

## Model Download

BiRefNet (RMBG-2.0) must be placed at `local/models/RMBG-2.0/`. Required files: `BiRefNet_config.py`, `birefnet.py`, `model.safetensors`.

```bash
pip install modelscope
modelscope download --model AI-ModelScope/RMBG-2.0 --local_dir local/models/RMBG-2.0
```
