## Context

当前 `rmbg_process.py` 的模型加载走 `importlib.util` 手动加载路径：创建 `_rmbg_model` 虚拟包 → 导入 `BiRefNet_config.py` → 导入 `birefnet.py` → 遍历类找 `PreTrainedModel` 子类 → `safetensors.torch.load_file` 加载权重。这是早期 HuggingFace `AutoModelForImageSegmentation` 尚未支持 RMBG-2.0 时的方案。当前 `transformers` 版本已原生支持 `trust_remote_code=True`，模型目录中 `config.json` / `preprocessor_config.json` / `BiRefNet_config.py` / `birefnet.py` / `model.safetensors` 齐全，`from_pretrained` 可直接加载。

参考实现：`/Users/tobeychao/Documents/Projects/rmbg-2.0-demo/app.py` 第 39-41 行。

## Goals / Non-Goals

**Goals:**
- `load_model()` 用 `AutoModelForImageSegmentation.from_pretrained()` 替代手动 importlib 加载，减少 ~50 行脆弱代码
- `process_image()` 简化模型输出处理，对齐官方 `preds[-1].sigmoid().cpu()` 模式
- 移除 threshold 二值化逻辑：sigmoid 输出直接作为连续 alpha 通道（对齐官方），edge_refine / white_bg 代码保留但默认 False
- `app.py` rmbg Tab 移除高级选项控件，简化参数传递

**Non-Goals:**
- 不支持从 HuggingFace Hub 在线下载模型（`local_files_only=True`）
- 不引入 `loadimg` 依赖
- 不删除高级功能的代码实现（保留待后续恢复）
- 不改 `main.py`、`core/state.py`、`core/skills.py`

## Decisions

### 1. 模型加载：`AutoModelForImageSegmentation.from_pretrained(local_files_only=True)`

**选择**：使用 HuggingFace transformers 原生 API 加载。

**替代方案评估**：
- 保持当前 importlib 方案：维护成本高，`birefnet.py` 类名变更或结构调整会导致加载失败
- 用 `from_pretrained` 不加 `local_files_only`：允许从 HF Hub 下载，但用户明确表示当前不需要

**风险**：`trust_remote_code=True` 执行模型仓库中的自定义代码，但 `local_files_only=True` 确保只加载已下载到本地的文件，不涉及远程代码执行。

### 2. `load_model()` 返回值保持 `(model, device)` 元组

接口不变，`ModelRegistry.get_or_load()` 和 `app.py` 的调用方无需修改。device 从 `model.device` 推断。

### 3. 移除 threshold 二值化，sigmoid 连续 alpha

官方 demo 不做二值化，sigmoid 输出直接作为 alpha 通道（连续 0-1 值）。threshold 相关的二值化代码**注释保留**而非删除，方便后续恢复。edge_refine / white_bg 同理：代码注释保留，默认走 False 分支。

### 4. `app.py` 不删高级选项控件，而是注释

三个高级选项控件（rmbg_threshold / rmbg_edge / rmbg_whitebg）及对应的事件绑定**注释保留**。回调直接传 False。后续恢复时取消注释即可。

## Risks / Trade-offs

- `from_pretrained` 首次加载需解析 `BiRefNet_config.py` 和 `birefnet.py`，加载行为可能与手动方式有微小差异（如 dtype 默认值） → 验证：对比新旧方案输出 mask 是否一致
- `model.safetensors` 权重加载从手动 `load_file` 变为 transformers 内部加载 → 实际更可靠，transformers 团队已测试过此路径
- GPU 回退逻辑目前写在 `process_image()` 中（MPS/CUDA OOM 回退 CPU） → `from_pretrained` 的 `.to(device)` 阶段也可能 OOM，需保留 try/except 回退
