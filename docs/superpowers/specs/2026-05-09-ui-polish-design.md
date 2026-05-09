# UI 精修设计文档

**日期**：2026-05-09
**目标**：在保留现有 6-Tab Gradio 架构的前提下，通过换主题 + 逐 Tab 密度调整，提升视觉精致度和信息密度合理性。
**范围**：仅改 `app.py`，不改 `core/`、`main.py`、`tests/`。
**参考**：`.claude/gradio-notes.md`（Gradio 6 主题/布局 API 速查）

---

## 0. 约束与边界

**做**：
- `app.py:launch()` 换主题
- 逐 Tab 调整控件高度、添加 `info=`、折叠低频参数至 Accordion

**不做**：
- 不引入自定义 CSS 文件（只保留现有极少量 `#title`/`.footer` CSS）
- 不改架构（不加 sidebar、不加历史画廊、不加进度条）
- 不动 `core/`、`tests/`、`main.py`
- 不加暗色切换
- 不改 Tab 顺序或 Tab 标签文字

---

## 1. 主题

### 1.1 目标效果

Ocean 主题水平渐变按钮 + indigo 强调色 + Inter 字体，整体现代专业感，优于现在的 Soft 默认。

### 1.2 具体改动（`app.py` 末尾 `launch()` 调用）

当前：
```python
app.launch(server_name="127.0.0.1", server_port=7861, share=False, css=CSS, theme=gr.themes.Soft())
```

改为：
```python
THEME = gr.themes.Ocean(
    primary_hue="indigo",
    radius_size="md",
    text_size="md",
    font=gr.themes.GoogleFont("Inter"),
    font_mono=gr.themes.GoogleFont("JetBrains Mono"),
).set(
    block_shadow="0 1px 3px rgba(0,0,0,0.06)",
    block_border_width="1px",
    button_primary_background_fill_hover="*primary_400",
)

app.launch(server_name="127.0.0.1", server_port=7861, share=False, css=CSS, theme=THEME)
```

`CSS` 常量保留（只有 `#title`/`.footer` 两条，不影响主题）。

---

## 2. Tab 2 · 去背景（rmbg）

### 2.1 问题

模型路径、阈值、边缘/白底 checkbox 与上传图挤在同侧，模型路径几乎从不改变。

### 2.2 改后结构

```
with gr.Tab("🎯 去背景"):
  gr.Markdown("### BiRefNet 深度学习去背景")
  with gr.Row():
    with gr.Column(scale=1):
      rmbg_input = gr.Image(label="上传图片", type="pil", height="45vh")
      rmbg_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
      with gr.Accordion("⚙ 高级选项", open=False):
        rmbg_model_dir = gr.Textbox(label="模型目录", value=..., info="BiRefNet 模型文件目录，通常无需修改")
        rmbg_threshold = gr.Slider(
            label="二值化阈值", minimum=0.3, maximum=0.7, value=0.5, step=0.05,
            info="0.3–0.4 保留发丝细节；0.5 平衡；0.6–0.7 边缘更干净"
        )
        with gr.Row():
          rmbg_edge = gr.Checkbox(label="边缘优化", value=True,
                                  info="高斯平滑 mask 边缘，去锯齿，处理时间约增加 10%")
          rmbg_whitebg = gr.Checkbox(label="白底输出", value=False,
                                     info="输出白色背景 RGB 图而非透明 PNG，适合直接打印")
    with gr.Column(scale=1):
      rmbg_output = gr.Image(label="结果", type="pil", height="45vh",
                             format="png", image_mode="RGBA", buttons=["fullscreen"])
      rmbg_status = gr.Textbox(label="状态", interactive=False, lines=1)
```

**关键变化**：
- `height=300` → `height="45vh"`（视口自适应）
- 模型路径 / 阈值 / 两个 checkbox → 收进 Accordion，`open=False`
- 按钮移到图片下方（比现在在参数区底部更合理）
- 状态 Textbox 改 `lines=1`

---

## 3. Tab 3 · 黑白差分（bwdiff）

### 3.1 问题

height=250 在主流 1080p 屏幕偏小。

### 3.2 改后结构

主结构保持三列不变，仅：
- 三张图高度 250 → `height="35vh"`
- `gr.Markdown` 副标题保留（已足够简洁）
- 状态 Textbox 改 `lines=1`（bwdiff 状态消息短，单行够用）

---

## 4. Tab 4 · 生黑白底（bwgen）

### 4.1 问题

prompt 没有引导信息；三个 Dropdown 含义不明；图片高度固定 250。

### 4.2 改后结构

控件顺序不变，补充 `info=` 和 `placeholder`：

```python
bwgen_prompt = gr.Textbox(
    label="主体描述",
    placeholder="例如：一把发光的魔法剑、一只蓬松的白猫",
    lines=2,
    info="描述主体即可，无需提到背景。系统自动添加黑/白背景指令。",
)
bwgen_ratio = gr.Dropdown(
    label="宽高比", choices=RATIO_CHOICES, value="1:1",
    info="1:1 通用；16:9 横屏壁纸；9:16 手机壁纸"
)
bwgen_size = gr.Dropdown(
    label="分辨率", choices=SIZE_CHOICES, value="1K",
    info="1K=1024px；2K=2048px；4K 仅 Wan2.7 支持"
)
bwgen_model = gr.Dropdown(
    label="模型", choices=MODEL_CHOICES, value="gemini",
    info="Gemini 速度快；Wan2.7 质量更高、支持 4K"
)
```

图片高度 250 → `height="38vh"`；状态 Textbox 保持 `lines=2`（消息含文件路径，多行）。

---

## 5. Tab 5 · 生图（gen-image）

### 5.1 改后结构

与 bwgen 相同的 `info=` 补充方式：

```python
genimg_prompt = gr.Textbox(
    label="提示词（英文效果更佳）",
    placeholder="例如：a glowing magic sword on black background, fantasy art style",
    lines=2,
    info="描述主体、风格、氛围；英文提示词效果通常优于中文。",
)
genimg_ratio = gr.Dropdown(label="宽高比", ..., info="1:1 通用；16:9 横屏壁纸；9:16 手机")
genimg_size  = gr.Dropdown(label="分辨率", ..., info="1K=1024px；2K=2048px；4K 仅文生图")
genimg_model = gr.Dropdown(label="模型",   ..., info="Gemini 速度快；Wan2.7 质量更高")
```

结果图高度 350 → `height="50vh"`（单图可给足空间）；状态 `lines=2`（消息含文件路径）。

---

## 6. Tab 6 · 一键管线（pipeline）

### 6.1 问题

4 列挤在一行（prompt 区 + 黑底 + 白底 + 结果各 height=200），图片如邮票大小。

### 6.2 改后结构（两行布局）

```
with gr.Tab("🔄 一键管线"):
  gr.Markdown("### bwgen → bwdiff 一键抠图")

  # 行 1：输入区（全宽）
  with gr.Row():
    with gr.Column(scale=2):
      pipe_prompt = gr.Textbox(label="主体描述", placeholder="例如：一把发光的剑", lines=2,
                               info="描述主体即可，系统自动生成黑底图和白底图后完成抠图。")
      with gr.Row():
        pipe_ratio = gr.Dropdown(label="宽高比", ...)
        pipe_size  = gr.Dropdown(label="分辨率", ...)
        pipe_model = gr.Dropdown(label="模型",   ...)
      pipe_btn = gr.Button("▶ 一键执行", variant="primary", size="lg")
    with gr.Column(scale=1):
      gr.Markdown("""
      **流程说明**
      1. 根据描述生成黑底 + 白底图（bwgen）
      2. 黑白差分计算 alpha 通道（bwdiff）
      3. 输出带透明通道的 PNG

      适合：需要快速从文字描述得到带透明背景素材的场景。
      """)

  # 行 2：三图并排
  with gr.Row():
    with gr.Column(scale=1):
      pipe_black = gr.Image(label="黑底图", type="pil", height="35vh",
                            format="png", buttons=["fullscreen"])
    with gr.Column(scale=1):
      pipe_white = gr.Image(label="白底图", type="pil", height="35vh",
                            format="png", buttons=["fullscreen"])
    with gr.Column(scale=1):
      pipe_result = gr.Image(label="抠图结果", type="pil", height="35vh",
                             format="png", image_mode="RGBA", buttons=["fullscreen"])

  pipe_status = gr.Textbox(label="状态", interactive=False, lines=2)  # 含文件路径，保持多行
```

**关键变化**：
- 4 列横排 → 2 行（输入行 + 图片行）
- 右侧 `scale=1` Column 放流程说明文字（替代现在的标题 Markdown）
- 三图高度 200 → `height="35vh"`，各占 ⅓ 宽
- 状态 `lines=1`

---

## 7. Tab 1 · 设置

**不动**。当前密度合理，主题自动带入新样式。

---

## 8. 手动验证 checklist

- [ ] `python main.py` 正常启动，6 Tab 可切换
- [ ] Ocean 主题视觉生效（按钮有渐变，字体为 Inter）
- [ ] rmbg Accordion 默认折叠；展开后控件完整
- [ ] rmbg 在 1080p 下不需要滚动即可看到按钮和结果
- [ ] pipeline 两行布局：输入在上，三图在下
- [ ] bwgen/gen-image Dropdown 悬停时 `info=` tooltip 可见
- [ ] 状态 Textbox 在 `lines=1` 下单行显示
- [ ] bwdiff 三图在 1080p 下不需要滚动
- [ ] 设置 Tab 行为不变

---

## 9. 风险与回退

| 风险 | 缓解 |
|------|------|
| `gr.themes.GoogleFont("Inter")` 需联网加载 | 离线环境会回退系统字体，功能不受影响 |
| `height="45vh"` 在极小窗口（< 768px）图片过小 | 可接受，工具类应用桌面优先 |
| Ocean 主题风格不如预期 | 只改 1 行 `THEME =`，回退秒级 |
| Accordion 折叠后 rmbg_model_dir 读取失败 | 控件仍在 DOM 中，Gradio State 正常，不影响 |
