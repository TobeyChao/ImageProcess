## Why

当前 `rmbg_process.py` 用 70 行 `importlib` 手动加载 BiRefNet 模型（创建虚拟包、手动导入 config/module、手动加载 safetensors），而 HuggingFace `transformers` 的 `AutoModelForImageSegmentation.from_pretrained()` 用 5 行即可完成同样工作。这段手动加载代码是项目早期 HuggingFace 尚未原生支持 RMBG-2.0 时的临时方案，现在官方的 `trust_remote_code=True` 路径已经稳定，是时候对齐官方，降低维护成本和潜在的兼容性风险。

## What Changes

- `rmbg_process.py` `load_model()`: 用 `AutoModelForImageSegmentation.from_pretrained(model_dir, trust_remote_code=True, local_files_only=True)` 替代手动 importlib 加载，约 50 行 → 5 行
- `rmbg_process.py` `process_image()`: 简化模型输出处理逻辑，对齐官方 demo 的 `preds[-1].sigmoid().cpu()` 模式
- `rmbg_process.py` `process_image()`: 移除 threshold 二值化逻辑，sigmoid 输出直接作为连续 alpha 通道（对齐官方 demo）
- `rmbg_process.py` `process_image()`: edge_refine / white_bg 两个参数代码保留但默认 False，后续逐步恢复
- `app.py` rmbg Tab: 移除高级选项控件（rmbg_threshold / rmbg_edge / rmbg_whitebg），简化回调函数参数列表

## Capabilities

### New Capabilities

- `rmbg-model-loading`: 用 HuggingFace transformers 原生 API 加载 BiRefNet 模型，替代手动 importlib 方案

### Modified Capabilities

<!-- No existing specs are modified by this change -->

## Impact

- `.claude/skills/rmbg/scripts/rmbg_process.py` — `load_model()` 和 `process_image()` 主要重构
- `app.py` — rmbg Tab UI 简化，移除高级选项控件，回调函数参数减少
- `core/state.py` — `ModelRegistry` 无需改动（接口兼容：`load_model(model_dir)` 仍返回 `(model, device)`）
- `core/skills.py` — 无需改动
- `main.py` — 无需改动
