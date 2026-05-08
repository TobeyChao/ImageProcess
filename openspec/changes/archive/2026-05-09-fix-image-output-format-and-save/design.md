## Context

Gradio 6.14.0 的 `gr.Image` 组件默认 `format="webp"` 和 `image_mode="RGB"`，这与项目生成的透明 PNG (RGBA) 图片不兼容。内置 download 按钮在 Gradio 6.x 中可能触发页面跳转而非下载。此外 `app.py` 中 rmbg、bwdiff、pipeline 的处理函数只返回 PIL Image 对象给前端展示，从未将结果写入磁盘。

## Goals / Non-Goals

**Goals:**
- 所有 `gr.Image` 显式设置 `format="png"`，透明输出额外设置 `image_mode="RGBA"`
- 用 `gr.DownloadButton` 替代 Gradio 内置 download 按钮
- rmbg/bwdiff/pipeline 的处理结果自动保存到 `local/output/<类别>/`

**Non-Goals:**
- 不修改 CLI 脚本
- 不改变输出目录结构
- 不增加用户可选输出格式（本次只修复默认格式）

## Decisions

### 1. format 和 image_mode 分层设置

对所有 `gr.Image` 设置 `format="png"`。仅对处理透明结果的组件（`rmbg_output`、`bwdiff_result`、`pipe_result`）额外设置 `image_mode="RGBA"`。bwgen 的黑底图/白底图、gen-image 的生成图不设 RGBA（它们输出为不透明 RGB）。

### 2. 关闭内置按钮，添加 DownloadButton

每个结果图下方添加对应的 `gr.DownloadButton`。`gr.DownloadButton` 接收文件路径字符串，前端点击时触发浏览器原生下载（`<a download>` 语义），不会跳转页面。

按钮布局：
```
┌──────────────────┐
│   gr.Image       │  ← buttons=["fullscreen"] (仅保留全屏)
└──────────────────┘
┌──────────────────┐
│ 💾 下载结果 PNG   │  ← gr.DownloadButton（新增）
└──────────────────┘
```

### 3. 处理函数返回值扩展

为支持 DownloadButton，处理函数需要在返回 PIL Image 的同时返回文件路径：

| Tab | 函数 | 变更前返回值 | 变更后返回值 |
|-----|------|-------------|-------------|
| rmbg | `rmbg_process` | `(Image, str)` | `(Image, str, str)` 增加 filepath |
| bwdiff | `bwdiff_process` | `(Image, str)` | `(Image, str, str)` 增加 filepath |
| bwgen | `bwgen_generate` | `(Image, Image, str)` | `(Image, Image, str, str, str)` 增加两个 filepath |
| gen-image | `genimg_generate` | `(Image, str)` | `(Image, str, str)` 增加 filepath |
| pipeline | `pipeline_run` | `(Image, Image, Image, str)` | `(Image, Image, Image, str, str, str, str)` 增加三个 filepath |

### 4. 自动存盘逻辑复用

rmbg 的自动存盘在 `rmbg_process` 函数内完成，使用 PIL 的 `result.save()` 写入 `local/output/rmbg/`。bwdiff/pipeline 同理写入对应目录。bwgen 和 gen-image 的底层脚本已自动存盘，无需重复。

## Risks / Trade-offs

- **返回值变更**：处理函数的 output 列表需要与新增的 DownloadButton 组件数量匹配，Gradio 按位置对应。如果数量不对会报错或下载内容错位。→ 逐 Tab 验证每个函数的 outputs 列表与返回值数量一致。
- **PNG 文件体积**：比 WebP 大。→ 本工具处理的是用户上传的图片，PNG 保真度更重要；WebP 对透明支持不一致，PNG 是正确选择。
