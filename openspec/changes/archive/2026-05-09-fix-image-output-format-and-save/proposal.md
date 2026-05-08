## Why

Gradio 6.x 的 `gr.Image` 默认 `format="webp"` 且 `image_mode="RGB"`，导致透明 PNG 被转码为 WebP 并丢失 alpha 通道（透明变白底）。同时内置 download 按钮点击后会触发页面跳转而非文件下载，丢失所有未保存的编辑状态。此外 rmbg/bwdiff/pipeline 的处理结果从未存盘，用户一旦刷新页面结果就丢失。

## What Changes

- 所有 `gr.Image` 显式设置 `format="png"`，透明输出组件设置 `image_mode="RGBA"`
- 关闭 Gradio 内置 download 按钮，改用 `gr.DownloadButton` 提供可靠的文件下载
- rmbg 处理结果自动保存到 `local/output/rmbg/`
- bwdiff 处理结果自动保存到 `local/output/bwdiff/`
- pipeline 的 bwdiff 结果自动保存到 `local/output/bwdiff/`
- 处理完成后展示可点击的输出文件路径

## Capabilities

### New Capabilities

（无新增能力，属于对现有 UI 的 bug 修复和体验增强）

### Modified Capabilities

- `web-ui`: 去背景/黑白差分/一键管线的处理结果增加自动存盘；所有 Image 组件显式指定 PNG 格式和正确的色彩模式；下载方式从内置按钮改为 DownloadButton。

## Impact

- `app.py` — 修改所有 `gr.Image` 组件参数，修改处理函数的返回值结构以支持 DownloadButton，添加自动存盘逻辑
- 输出目录新增文件：`local/output/rmbg/`、`local/output/bwdiff/`（目录已存在，新增实际文件）
- 不涉及 API、依赖、CLI 脚本变更
