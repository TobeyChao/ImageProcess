# Gradio 6 速查（项目级）

本项目用 Gradio 6.x。以下笔记是从官方 guides 抽出的可操作要点 + 本项目踩过的坑，给未来改 UI 时参考。

来源：
- [Theming Guide](https://www.gradio.app/guides/theming-guide)
- [Controlling Layout](https://www.gradio.app/guides/controlling-layout)
- [Custom CSS and JS](https://www.gradio.app/guides/custom-CSS-and-JS)
- [Blocks and Event Listeners](https://www.gradio.app/guides/blocks-and-event-listeners)

---

## 1. 主题（先调主题，再写 CSS）

### 1.1 8 个核心构造参数

```python
gr.themes.Soft(
    primary_hue="indigo",     # 强调色（按钮、滑块、激活态）
    secondary_hue="slate",    # 次要色
    neutral_hue="slate",      # 文字、边框、背景灰阶
    spacing_size="md",        # sm / md / lg —— 控件内 padding 与控件间距
    radius_size="md",         # none / sm / md / lg —— 圆角
    text_size="md",           # sm / md / lg
    font=gr.themes.GoogleFont("Inter"),
    font_mono=gr.themes.GoogleFont("JetBrains Mono"),
)
```

90% 的"换一种感觉"靠这 8 个参数，不用写 CSS。

### 1.2 8 个预置主题各自的味道

| 主题 | 默认主色 | 性格 | 适合 |
|------|---------|------|------|
| `Base` | 蓝 | 极简，给定制做基底 | 完全自定义起点 |
| `Default` | 橙/灰 | Gradio 5 标配，鲜艳 | 通用 |
| `Origin` | 沉稳 | Gradio 4 风，保守 | 怀旧 / 文档型 |
| `Citrus` | 黄 | 焦点态明显，按钮按下有 3D | 偏玩乐、互动重 |
| `Monochrome` | 黑白 | 衬线字体，报纸感 | 严肃、文档 |
| `Soft` | 紫/白 | 圆角大、留白多 | 友好、消费向 |
| `Glass` | 蓝 + 半透明 | 垂直渐变，玻璃感 | 现代深色 |
| `Ocean` | 蓝绿 | 水平渐变，按钮华丽 | 现代亮色 |

**本项目目前用 `Soft`**。如果想要更精致一点不动结构，可以先把 `Soft` 换成 `Ocean` / `Glass` / `Citrus` 试感觉。

### 1.3 用 `.set()` 微调 CSS 变量

```python
theme = gr.themes.Soft(primary_hue="indigo").set(
    button_primary_background_fill="*primary_500",
    button_primary_background_fill_hover="*primary_400",
    block_shadow="0 1px 3px rgba(0,0,0,0.06)",
    block_border_width="1px",
)
```

引用规则：
- `*primary_300` → 引用核心色阶（50–950）
- `*button_primary_background_fill` → 引用其他变量
- `_dark` 后缀 → 暗色模式独立值，不写则继承亮色

常用变量：`button_primary_*`、`block_shadow`、`block_border_width`、`block_title_text_weight`、`body_background_fill`、`input_background_fill`。

---

## 2. 布局（不用 sidebar 也能做出层次）

### 2.1 Row / Column / scale / min_width

```python
with gr.Row(equal_height=True):
    with gr.Column(scale=1, min_width=300):  # 左侧参数区
        ...
    with gr.Column(scale=2, min_width=400):  # 右侧结果区，2 倍宽
        ...
```

- `scale=0`：不抢空间
- `scale=N`：按比例分配剩余空间
- `min_width`：低于此值自动换行

### 2.2 Tabs / Tab

连续的 `gr.Tab(...)` 自动归到同一组：

```python
with gr.Tabs() as tabs:
    with gr.Tab("A", id="a"):
        ...
    with gr.Tab("B", id="b"):
        ...
```

切到指定 Tab：在 click 中返回 `gr.Tabs(selected="b")` 即可。

### 2.3 Accordion（折叠"高级选项"）

```python
with gr.Accordion("高级参数", open=False):
    threshold = gr.Slider(...)
```

降低视觉密度的最低成本手段。

### 2.4 Group（视觉打包）

`gr.Group()` 把内部组件视觉上合并成一组（共享背景、去除内部间距），适合"一个上传 + 一个按钮"这种紧密单元。

### 2.5 Sidebar（如果真要左导航）

```python
with gr.Sidebar(position="left", open=True):
    ...
```

注意：本项目此前尝试过 sidebar + 自定义 CSS 重做布局，**失败**——和原生 Gradio 控件斗气，按钮样式压不住，整体反而更丑。后来回退到原生 6-Tab 横向布局。Sidebar 适合"参数侧栏 + 大结果区"这种结构（如 chatbot），不适合多功能切换。

### 2.6 动态可见性

```python
with gr.Column(visible=False) as panel:
    ...

btn.click(
    lambda: gr.Column(visible=True),  # 直接返回新 layout 实例
    outputs=panel,
)
```

也可以返回字典选择性更新：

```python
def handler():
    return {
        out_a: "新值",
        out_b: gr.update(visible=True),
        # 不在 dict 里的输出保持原状
    }
```

---

## 3. 自定义 CSS / JS（最后手段）

### 3.1 注入方式

```python
demo.launch(css="...string...")
demo.launch(css_paths=["theme.css", "extras.css"])  # 文件
```

### 3.2 安全选择器：`elem_id` / `elem_classes`

```python
gr.Button("Run", elem_id="run-btn", elem_classes="primary-action")
```

CSS 里 `#run-btn` / `.primary-action` 比 `button.lg` 这种内置选择器更**抗版本升级**。Gradio 升级会改 DOM 结构和 class 名，但你自己加的 id/class 不会被改。

### 3.3 引用主题变量

CSS 里可以用 `var(--primary-500)`、`var(--block-shadow)` 等，跟主题保持一致。

### 3.4 JS

- `gr.Blocks(js="...")` → 加载时执行
- `btn.click(..., js="(x) => x.toUpperCase()")` → 事件前置 JS
- `gr.Blocks(head="<meta ...>")` → 注入 `<head>`

**坑**：自己用 `getElementById` / `querySelector` 改 DOM 风险高，跨版本易碎。能用 `gr.update()` 解决就别写 JS。

---

## 4. 事件 / 状态 / 进度

### 4.1 多输出更新

返回元组按 outputs 顺序，或返回 dict 选择性更新：

```python
btn.click(fn, inputs=[a, b], outputs=[c, d, e])

def fn(a, b):
    return c_value, d_value, e_value          # tuple
    # 或
    return {c: c_value, e: gr.update(...)}    # 选择性
```

### 4.2 不想覆盖某个输出

```python
return gr.skip()    # 保持原值
return None         # 清空
```

### 4.3 链式

```python
btn.click(step1, ...).then(step2, ...).success(step3, ...)
```

`.then()` 总是执行；`.success()` 只在前一步未抛错时执行。

### 4.4 Per-session State

```python
state = gr.State(initial_value)

def handler(input, current_state):
    new_state = ...
    return output, new_state

btn.click(handler, [input, state], [output, state])
```

**关键**：`gr.State` 是 per-session 的，多浏览器标签互不影响。模块级全局变量则**会跨标签共享**——本项目以前 bwdiff 用模块级 `_TMP_BLACK` 缓存图，多标签互相覆盖，是 bug。

### 4.5 进度条

```python
def fn(x, progress=gr.Progress()):
    progress(0.1, desc="加载模型...")
    ...
    progress(1.0, desc="完成")
```

### 4.6 启动时事件

```python
demo.load(fn, inputs=None, outputs=...)  # 页面加载时跑
```

---

## 5. 本项目踩过的坑（重要）

1. **不要从零自己拼 sidebar 布局**：原生控件的圆角、阴影、按钮样式会和你的自定义 CSS 互相覆盖，越改越丑。优先调主题，不行再 elem_id 局部覆盖。
2. **不要把"调主题"和"改架构"混在一个 PR**：主题换法 30 行代码，结构改动几百行，混在一起回退困难。
3. **6 个 Tab 的横向布局比左侧导航更适合本项目**——Tab 数固定、每个 Tab 都是独立任务，不是设置/导航关系。
4. **`launch()` 接收 `theme=`、`css=`、`js=`**，不是 `gr.Blocks()`（Gradio 6 改动）。本项目 `app.py` 末尾 `app.launch(...)` 已正确。
5. **模型缓存放 `core/state.ModelRegistry`**（840MB 模型不可能 per-session），但**上传图等用户数据**必须用 `gr.State` 或直接走 `gr.Image` 输入参数，不能模块级全局。

---

## 6. 改 UI 的建议优先级

由低风险到高风险：

1. **换主题构造参数**（`primary_hue`、`radius_size`、`font`）—— 几行，立刻有变化
2. **加 `info=`、`placeholder`、`examples=`** —— 信息密度提升，零风险
3. **`gr.Accordion` 收起高级参数** —— 视觉降噪
4. **`.set()` 调几个关键 CSS 变量**（按钮主色、阴影、边框）—— 精致度
5. **`elem_id` + 局部 CSS** —— 微调特定区域
6. **整体布局重构（sidebar / 自定义网格）** —— 高风险，避免

每一档都能独立验证后再决定要不要进下一档。
