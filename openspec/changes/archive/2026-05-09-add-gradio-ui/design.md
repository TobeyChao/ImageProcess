## Context

当前项目通过 CLI 脚本（`rmbg_process.py`、`bw_diff.py`、`bw_gen.py`、`gen_image.py`）提供四个图片处理功能。用户通过命令行传参或 Claude Code Skill 工具调用。环境初始化需手动执行多个步骤（创建 venv、安装依赖、下载模型、配置 API Key），缺乏统一的初始化流程。

本项目仅本机使用，无需考虑多用户、鉴权、网络部署等问题。

## Goals / Non-Goals

**Goals:**
- 提供浏览器端 Web UI，参数通过滑块/下拉/拖拽配置，消除命令行输入错误
- 零依赖启动脚本 `main.py`，自动检测环境、引导初始化，所有步骤实时推送日志和进度
- 参数持久化（模型路径、API Key）到 `local/config.json`
- 一键管线：bwgen→bwdiff 自动串联
- 四个处理脚本重构为可复用函数，CLI 和 UI 共享同一套核心逻辑
- 模型下载切换到 ModelScope

**Non-Goals:**
- 不支持远程访问或多人使用（仅 localhost）
- 不添加用户认证
- 不改动 game-ui-analyzer 技能（纯 prompt，无脚本）
- 不改变 CLI 接口

## Decisions

### 1. Gradio 作为 UI 框架

**选择**：Gradio（`gradio.Blocks`），而非 Streamlit / Flask / FastAPI。

**理由**：
- Python 原生，与现有技术栈一致；图片上传/预览/下载组件开箱即用；`gr.Slider`、`gr.Dropdown`、`gr.Image` 等组件直接映射到参数
- Streamlit 偏向数据展示，对图片处理流程的支持不如 Gradio 直观
- Flask/FastAPI 需要自建前端，工作量大，且项目无需 API 化

### 2. 双进程架构：main.py + app.py

**选择**：`main.py`（纯 stdlib 引导器）→ `app.py`（Gradio 应用）。

```
main.py (stdlib only)
│
├─ [阶段一] 环境检测
│   ├─ Python ≥ 3.10 检查
│   ├─ .venv 检查（不存在则创建）
│   ├─ 依赖检查（尝试 import gradio, torch 等）
│   └─ 模型检查（local/models/RMBG-2.0/model.safetensors 是否存在）
│
├─ [阶段二] 初始化向导（有缺失时）
│   ├─ 启动 http.server (localhost:7860)
│   ├─ 提供 setup.html 页面 → 用户点"一键初始化"
│   ├─ POST /api/setup → subprocess 执行安装任务
│   └─ GET /api/events → SSE 实时推送 stdout
│
└─ [阶段三] 启动 Gradio
    ├─ subprocess: python app.py --port 7861
    └─ main.py 转发请求到 localhost:7861（反向代理）
```

**理由**：`main.py` 需要零依赖，确保用户 clone 后 `python main.py` 即可启动。Gradio 应用在依赖装好后作为子进程运行。

**替代方案**：全部写在一个 `app.py` 里，依赖 Gradio 做初始化 UI。不可行——Gradio 本身需要 pip install，鸡生蛋问题。

### 3. 脚本重构策略

**选择**：最小化重构——将核心逻辑封装为函数，CLI 参数解析和输出路径拼接保留在 `if __name__ == "__main__"` 块中。

```python
# rmbg_process.py 重构后
def load_model(model_dir, device=None):
    """返回 (model, device)"""

def process_image(input_path, model, device, threshold=0.5,
                  edge_refine=True, white_bg=False):
    """返回 PIL.Image (RGBA 或 RGB)"""

if __name__ == "__main__":
    # argparse + 调用上述函数 + save
```

**理由**：Gradio UI 直接 `from skills.rmbg.scripts.rmbg_process import load_model, process_image`，不重复实现。CLI 向后兼容。

### 4. API Key 持久化

**选择**：`local/config.json`，优先级：UI 输入值 > 环境变量。

```json
{
  "model_dir": "/path/to/local/models/RMBG-2.0",
  "gemini_api_key": "sk-...",
  "dashscope_api_key": "sk-..."
}
```

**理由**：脱离 Claude Code 的 `settings.local.json` 依赖，直接用 `json.load/dump`。密码字段类型 `password`，浏览器端遮挡。

### 5. 模型下载方案

**选择**：ModelScope Python SDK（`modelscope` 库）。

```python
from modelscope.hub.snapshot_download import snapshot_download
snapshot_download('AI-ModelScope/RMBG-2.0', local_dir=path,
                   callback=progress_callback)
```

**理由**：`snapshot_download` 提供 `callback` 参数，可接收下载进度（文件数、字节数），直接映射到 UI 进度条。相比 `huggingface-cli` 需要额外安装且无 Python 回调。

### 6. Tab 布局

```
┌──────────────────────────────────────────────────────┐
│  [设置] [去背景] [黑白差分] [生黑白底图] [生图] [管线]  │
└──────────────────────────────────────────────────────┘
```

设置 Tab 放第一个，API Key 和模型路径修改后即时生效。功能 Tab 依赖设置项，设置未配好时对应功能 Tab 给出提示。

### 7. 管线 Tab 设计

**选择**：前端串联，不写第八份脚本。

```
用户填写 prompt + 参数
  → 点击"一键执行"
    → 调用 bw_gen.generate_black_white()
      → 返回 (black_path, white_path)
    → 调用 bw_diff.bw_diff(black_path, white_path)
      → 返回 result_path
  → 三张图同时预览
```

bwgen 和 bwdiff 互相独立，管线仅组合调用，不引入新依赖。

## Risks / Trade-offs

- **Gradio 启动慢**：首次导入会加载 torch 等重依赖，冷启动 5-10 秒。→ 接受，启动后交互无延迟
- **模型下载 1.7GB**：ModelScope 下载可能较慢。→ 进度回调提供实时反馈，用户不会以为卡死
- **脚本重构引入 bug**：→ 重构后保留 CLI 入口，运行 `python rm_process.py -i <test> -m <model>` 验证等价性
- **反向代理性能**：`main.py` 用 stdlib `http.server` 转发请求，不适合高并发。→ 本机单用户，不影响体验
