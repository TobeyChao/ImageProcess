# App 全面重构设计文档

**日期**：2026-05-09
**目标**：对 `app.py`（491 行单文件 Gradio 应用）进行模块化重构、UI 重设计、鲁棒性强化、UX 提示完善，准备长期使用。
**实现路线**：守 Gradio 5.x + 重型自定义 CSS（保真度约 80–85%），不替换框架。

---

## 0. 现状与驱动

### 0.1 现状

`app.py` 单文件 491 行，包含：

- 6 个 Tab：设置 / 去背景 (rmbg) / 黑白差分 (bwdiff) / 生黑白底 (bwgen) / 生图 (gen-image) / 一键管线
- 通过 `_load_module` 反射加载 `.claude/skills/*/scripts/` 下的脚本
- 配置写到 `local/config.json`

### 0.2 已识别问题

| 类型 | 问题 | 位置 |
|------|------|------|
| Bug | bwdiff 用模块级全局变量 `_TMP_BLACK/_TMP_WHITE` 缓存上传图，多浏览器标签会互相覆盖 | app.py:137-150 |
| 重复 | API key 解析（读 config → 设环境变量 → 校验）在 3 处重复 | app.py:173-188, 203-216, 229-243 |
| 重复 | `pipeline_run` 把 `bwgen_generate` + `bwdiff_process` 的实现贴了一遍而非调用 | app.py:229-263 |
| UX | 错误提示直接吐异常字符串 (`f"错误: {e}"`)，对用户无意义 | 全文 |
| UX | 长操作（生图 30s+）无进度反馈 | bwgen/gen/pipeline |
| UX | 缺示例、缺 tooltip、CSS 几乎为空 | 全文 |
| 架构 | `app.py` 491 行单文件，难以扩展 | 全文 |

### 0.3 已确认的需求

来自 brainstorming 对话：

- **驱动**：全面打磨，准备长期使用
- **新能力**：所有控件加 tooltip + 历史记录 / 生成画廊（不做提示词模板、不做批处理）
- **布局**：C 类型——左侧导航 + 主操作区 + 右侧历史画廊
- **历史存储**：持久化到 `local/history.json`，**不限制条数**
- **提示方式**：Toast 通知（用 Gradio 5.x 原生 `gr.Info/Warning/Error`）
- **主题**：亮色 + 暗色切换，持久化到 config
- **历史回填**：填回参数后**不自动执行**，用户手动触发
- **进度条**：**所有 view 都启用**
- **引导提示**：**常驻**，不因执行过隐藏
- **Gradio 版本**：用最新版（不锁定）

---

## 1. 模块结构

### 1.1 目标文件树

```
app.py                      # 入口，仅做 Blocks 组装 (~80 行)
ui/
  __init__.py
  theme.py                  # 主题、CSS 变量、亮/暗切换 JS
  layout.py                 # 三栏框架 (sidebar / main / history)
  toast.py                  # gr.Info/Warning/Error 封装 + 文案模板
  tooltips.py               # 所有 ? 提示文本集中管理
  views/
    __init__.py
    settings.py             # 设置 view
    rmbg.py                 # 智能去背景 view
    bwdiff.py               # 黑白差分 view
    bwgen.py                # 生黑白底 view
    gen_image.py            # AI 生图 view
    pipeline.py             # 一键管线 view（复用 bwgen + bwdiff）
core/
  __init__.py
  config.py                 # 配置文件读写 + schema 迁移
  history.py                # 历史 JSON 读写、缩略图、筛选
  api_keys.py               # 统一 API key 解析与上下文注入
  errors.py                 # 异常 → 友好文案翻译
  skills.py                 # skill 脚本加载封装（取代 _load_module）
  state.py                  # 模型懒加载单例 + 并发锁
tests/
  test_config.py
  test_history.py
  test_api_keys.py
  test_errors.py
  test_state.py
  test_views_pure.py
  fixtures/
    img_black.png
    img_white.png
    img_expected_alpha.png
```

### 1.2 关键改动

1. **修复 bwdiff 多标签 bug**：把上传图缓存 `_TMP_BLACK / _TMP_WHITE` 改成 `gr.State`（per-session）。**模型单例 `_loaded_model / _loaded_device` 保留全局**——BiRefNet ~840MB，跨 session 共享是必要的，不是 bug。统一封装到 `core/state.py` 的 `ModelRegistry`（threading.Lock 保护并发首次加载）。
2. **API key 处理统一**：`core/api_keys.py` 提供 `with use_api_key("gemini"): ...` 上下文管理器，3 处重复合一
3. **pipeline 复用而非复制**：`pipeline_run` 改为调用 `bwgen.generate(...)` 和 `bwdiff.compute(...)`
4. **错误层**：所有 `try/except` 经 `core.errors.user_message(e)` 翻译，常见错误给中文文案 + 操作建议，未知错误显示「类型: 原文 + 查看日志」

---

## 2. UI 框架与组件

### 2.1 三栏布局结构

```
gr.Blocks
  ├─ 顶栏 (gr.Row, sticky, 高 56px)
  │    ├─ Logo + 标题 "Image Processing Toolbox"
  │    └─ 状态徽章 [GPU/CPU] [Gemini Key] [DashScope Key] [🌓 主题切换]
  │
  ├─ 主体 (gr.Row, flex)
  │    ├─ 左导航 (gr.Sidebar, 宽 200px)
  │    │    ├─ 分组「抠图」: 智能去背景 / 黑白差分
  │    │    ├─ 分组「生图」: 生黑白底 / AI 生图
  │    │    ├─ 分组「流程」: 一键管线
  │    │    └─ 设置 (sticky bottom)
  │    │
  │    ├─ 主区 (gr.Column, flex=1)
  │    │    └─ 6 个 view 用 gr.Group + visible=True/False 切换
  │    │
  │    └─ 历史画廊 (gr.Column, 宽 220px)
  │         ├─ 筛选 chip: 全部 / 抠图 / 生图
  │         └─ gr.Gallery (列表模式)
  │
  └─ Toast 容器（Gradio 5.x 原生右上角浮层）
```

**导航联动**：sidebar 选项 → `gr.State("rmbg")` → 6 个 view 的 `visible` 属性绑定。

### 2.2 组件实现选择

| 组件 | 实现 | 说明 |
|------|------|------|
| Tooltip | `gr.Slider(info=...)` 等原生 `info` 参数；复杂的用 `gr.HTML` + `<abbr title=>` | 文案集中在 `ui/tooltips.py` |
| Toast | Gradio 5.x `gr.Info()/gr.Warning()/gr.Error()` | 原生支持右上角浮层 |
| 主题切换 | 顶栏按钮 → JS toggle `body[data-theme]` | CSS 变量响应 |
| 上传区 | `gr.Image(sources=["upload","clipboard"])` | 加 `image_mode="RGB"` 规范化 |
| 历史画廊 | `gr.Gallery(columns=1, allow_preview=True)` | 点击触发回填 |
| 状态徽章 | `gr.HTML` 实时渲染 | 启动时 + 设置保存后刷新 |
| 进度条 | `gr.Progress()` | 所有 view 启用 |

### 2.3 CSS 变量主题

```css
:root {
  --primary: #6366f1;
  --primary-grad: linear-gradient(135deg, #6366f1, #8b5cf6);
  --bg: #f7f8fa;
  --surface: #ffffff;
  --border: #ebeef3;
  --text: #1f2937;
  --text-mute: #6b7280;
  --success: #059669;
  --warn: #b45309;
  --error: #dc2626;
}
[data-theme=dark] {
  --bg: #0f1117;
  --surface: #1a1d27;
  --border: #2a2f3d;
  --text: #e5e7eb;
  --text-mute: #9ca3af;
}
```

### 2.4 提示文案样例

```python
TOOLTIPS = {
    "rmbg.threshold": "二值化阈值。0.3-0.4 保留更多发丝/绒毛细节；0.5 平衡；0.6-0.7 边缘更干净但可能丢失细节。",
    "rmbg.edge_refine": "对 mask 边缘做高斯平滑，避免锯齿。处理时间增加约 10%。",
    "rmbg.white_bg": "勾选后输出白色背景的 RGB 图（非透明 PNG），适合直接打印。",
    "bwdiff.upload": "黑底图和白底图必须同机位、同光照、同分辨率，仅背景颜色不同。",
    "bwgen.prompt": "描述主体即可，无需提到背景。系统会自动添加「placed on solid black/white background」。",
    "gen.ratio": "1:1 通用；16:9 横屏壁纸；9:16 手机壁纸；3:4 / 4:3 接近 A4。",
    "gen.size": "1K=1024px 长边；2K=2048px；4K 仅 Wan2.7 文生图支持，速度慢 2-4 倍。",
    "gen.model": "Gemini 速度快，DashScope (Wan2.7) 质量更高且支持 4K。",
    # 约 20-30 条
}
```

---

## 3. 数据与状态

### 3.1 历史 schema (`local/history.json`)

```json
{
  "version": 1,
  "entries": [
    {
      "id": "20260509_143022_a3f1",
      "timestamp": "2026-05-09T14:30:22",
      "type": "rmbg",
      "input": {
        "image_path": "local/output/rmbg/_input_20260509_143022.png",
        "params": {"threshold": 0.5, "edge_refine": true, "white_bg": false}
      },
      "output": {
        "image_path": "local/output/rmbg/cat_rmbg_20260509_143022.png",
        "extra_paths": null
      },
      "thumb_path": "local/output/.thumbs/20260509_143022_a3f1.webp",
      "prompt": null,
      "model": null
    }
  ]
}
```

**生命周期**：

- 每次成功处理后 append
- 缩略图 128px webp 存 `local/output/.thumbs/`，原图保留路径引用（不复制）
- **不限制条数**——用户决定何时清理
- 「清空历史」按钮：仅清 `history.json` 和缩略图，不动 `local/output/`

### 3.2 配置文件扩展 (`local/config.json`)

```json
{
  "model_dir": ".../local/models/RMBG-2.0",
  "gemini_api_key": "...",
  "dashscope_api_key": "...",
  "theme": "light",
  "last_view": "rmbg",
  "history_filter": "all",
  "default_model": "gemini",
  "default_ratio": "1:1",
  "default_size": "1K"
}
```

旧字段全保留；新字段缺失走默认值。

### 3.3 Gradio State 拓扑

```python
# 全局 (per-session)
current_view   = gr.State("rmbg")
theme          = gr.State("light")
history_data   = gr.State([])          # 启动从 JSON 加载

# 每个 view 内部
bwdiff_black   = gr.State(None)        # 替代 _TMP_BLACK（per-session）
bwdiff_white   = gr.State(None)        # 替代 _TMP_WHITE（per-session）

# 全局（模块级，跨 session 共享）
# rmbg 模型在 core/state.ModelRegistry 中，不放 gr.State
# BiRefNet ~840MB，per-session 加载会爆内存
```

### 3.4 历史回填流程

点击历史项 → `on_history_click(entry_id)`：

1. 读 entry，按 `type` 决定切到哪个 view
2. 更新 `current_view` State → 切 visible
3. 把 `entry.input.params` 写回该 view 输入控件
4. **不自动执行**，避免误触造成 API 费用
5. Toast: "已加载历史参数，点击 ▶ 重新执行"

### 3.5 并发安全

- `gr.State` per-session 隔离 → 多标签不会互相覆盖
- `history.json` 写入：`threading.Lock` + 原子写（写 `.tmp` 再 `os.replace`）
- 模型懒加载用 lock 保护首次并发

---

## 4. 错误处理与 UX 提示

### 4.1 错误模式表 (`core/errors.py`)

```python
ERROR_PATTERNS = [
    (FileNotFoundError, "找不到文件: {path}", "请检查路径是否正确"),
    (PermissionError, "没有权限访问: {path}", "尝试以管理员身份运行或检查文件权限"),

    (lambda e: "API key" in str(e).lower() or "401" in str(e),
     "API Key 无效或已过期", "请到「设置」检查 Key 是否正确"),
    (lambda e: "rate limit" in str(e).lower() or "429" in str(e),
     "API 调用太频繁，请稍后再试", "建议等待 30 秒"),
    (lambda e: "quota" in str(e).lower(),
     "API 配额已用完", "请检查 API 控制台账单"),

    (lambda e: "CUDA out of memory" in str(e),
     "显存不足", "尝试关闭其他占用 GPU 的程序，或在设置中改用 CPU"),
    (lambda e: "model.safetensors" in str(e),
     "模型文件缺失", "请先在设置页下载 BiRefNet 模型"),

    (lambda e: "size" in str(e).lower() and "differ" in str(e).lower(),
     "黑底图和白底图尺寸不一致", "请确认两张图来自同一拍摄"),
]

def user_message(exc: Exception) -> tuple[str, str]:
    """返回 (友好文案, 建议)，未匹配返回 (类型: 原文, '查看日志了解详情')"""
```

### 4.2 Toast 调用

```python
gr.Info("处理完成 ✓")              # 成功 (绿)
gr.Warning("API 配额仅剩 10%")     # 警告 (黄)
gr.Error("API Key 无效\n建议: ...") # 错误 (红，需手动关闭)
```

### 4.3 输入预校验

| 操作 | 预检查 | 失败提示 |
|------|--------|----------|
| rmbg | 模型目录 + safetensors 存在 | "请先到设置页下载模型" |
| rmbg | 输入图 < 50MB | "图片过大，建议 < 50MB" |
| bwdiff | 两图尺寸一致 | "尺寸不一致 (黑: X×Y, 白: X'×Y')" |
| bwdiff | 两图差异不全为 0 | "两图无差异，请确认是否上传错误" |
| bwgen/gen | API key 已配置 | "请先到设置页填写 {model} API Key" |
| bwgen/gen | prompt 非空 + < 2000 字符 | "提示词不能为空 / 过长" |
| pipeline | 综合上述 | 同上 |

### 4.4 进度条（所有 view 启用）

```python
def bwgen_run(prompt, ..., progress=gr.Progress()):
    progress(0.1, desc="正在生成黑底图...")
    ...
    progress(0.6, desc="正在生成白底图...")
    ...
    progress(1.0, desc="完成")
```

阶段示例：

- rmbg：加载模型 → 推理 → 后处理
- bwdiff：差分计算 → alpha 合成
- bwgen：生黑底 → 生白底
- gen：发送请求 → 等待响应 → 下载
- pipeline：bwgen 双图 → bwdiff 抠图

### 4.5 引导提示（常驻）

每个 view 始终显示：

- **rmbg**：上传区下方 "💡 适合人像、宠物、产品；复杂边缘建议开启「边缘优化」"
- **bwdiff**：两上传区之间 "需要同机位拍摄的两张图，分别是黑色和白色背景"
- **bwgen**：prompt placeholder 完整示例
- **gen**：placeholder 中英对照样例
- **pipeline**：顶部一句话流程说明

### 4.6 顶栏徽章实时性

- GPU/CPU：启动一次 (`torch.cuda.is_available()`)
- API Key：启动 + 设置保存后刷新
- 不轮询

---

## 5. 测试与迁移

### 5.1 测试覆盖

```
tests/
  test_config.py            # 读写 + env var 优先级 + schema 迁移
  test_history.py           # JSON schema + 原子写 + 并发
  test_api_keys.py          # 优先级 + 缺失提示
  test_errors.py            # ERROR_PATTERNS 匹配
  test_state.py             # 模型懒加载 lock
  test_views_pure.py        # view 函数纯逻辑（不启 Gradio）
  fixtures/                 # bwdiff 黄金对照图
```

**不测**：Gradio UI 渲染、实际 API 调用、BiRefNet 推理结果。

**跑测**：`pytest tests/ -v`，无 GPU/API key 依赖。

### 5.2 手动验证 checklist

- [ ] 6 个 view 切换顺畅，状态不串
- [ ] 多浏览器标签同时上传 bwdiff 不互相覆盖
- [ ] 主题切换瞬间生效，刷新后仍记住
- [ ] 历史回填后参数正确填回，不自动执行
- [ ] 所有 ? tooltip 文案显示正常，无 KeyError
- [ ] Toast 在成功/警告/错误三种场景颜色正确
- [ ] API key 错误显示中文提示，不暴露 raw exception
- [ ] 引导 placeholder 常驻，处理后不消失
- [ ] 历史画廊筛选 chip 工作正常
- [ ] 顶栏 GPU/Key 徽章状态准确
- [ ] CPU-only 环境下 rmbg 能跑
- [ ] 4K 生图进度条分阶段更新
- [ ] 历史 100+ 条不卡顿
- [ ] 暗色主题下所有文字对比度足够
- [ ] `python main.py` 全新克隆能完整跑通向导

### 5.3 PR 拆分

**PR 1 · 后端重构（无 UI 改动）**

- 拆 `core/` 模块
- 现有 `app.py` 改为 import 这些模块，UI 不变
- 干掉模块级全局变量
- pipeline 复用调用
- 新增 `tests/`
- 验收：现有 6 Tab 用户视角行为不变，但内部架构改了——bwdiff 多标签 bug 修复、代码量减少、可被 PR 2 复用

**PR 2 · UI 重写**（依赖 PR 1）

- 实现 C 布局：sidebar / main / history
- 主题系统、Toast、tooltip、引导提示
- 历史画廊 + 回填
- `app.py` 重写为 `ui/` 模块组装

**PR 3 · 抛光**（依赖 PR 2）

- 进度条全覆盖
- 输入预校验
- 错误模式表完善
- 手动验证清单全过

### 5.4 兼容性

- `local/config.json` 旧字段保留，新字段缺失走默认值
- `local/output/*` 目录结构不变
- 模型路径不变
- `requirements.txt` 无新依赖（gradio 已在；history 用 stdlib；缩略图用现有 pillow）

### 5.5 风险与回退

| 风险 | 缓解 |
|------|------|
| Gradio 5.x API 升级破坏现有调用 | PR 1 不动 UI，先验证后端 |
| `gr.Sidebar` 在某些场景表现不佳 | 备选：`gr.Column(scale=0, min_width=200)` 手搓 |
| 用户已有 config.json 字段冲突 | `core/config.py` 加 schema 迁移函数 |
| 历史 JSON 损坏导致启动失败 | 启动时 try/except，损坏则备份为 `.bak` 后新建 |
