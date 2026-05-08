## 1. Image 组件格式修复

- [x] 1.1 为所有输出 `gr.Image` 添加 `format="png"`（rmbg_output, bwdiff_result, bwgen_black, bwgen_white, genimg_output, pipe_black, pipe_white, pipe_result）
- [x] 1.2 为透明输出组件添加 `image_mode="RGBA"`（rmbg_output, bwdiff_result, pipe_result）
- [x] 1.3 所有输出 `gr.Image` 添加 `buttons=["fullscreen"]` 关闭内置下载/分享按钮

## 2. 自动存盘逻辑

- [x] 2.1 rmbg_process 增加保存到 `local/output/rmbg/<name>_rmbg.png`，返回原图名用于构造文件名
- [x] 2.2 bwdiff_process 增加保存到 `local/output/bwdiff/<timestamp>_bwdiff.png`
- [x] 2.3 pipeline_run 增加保存 bwdiff 结果到 `local/output/bwdiff/<timestamp>_pipeline.png`

## 3. DownloadButton 组件

- [x] 3.1 rmbg Tab：添加 `gr.DownloadButton`，更新函数 outputs 和返回值
- [x] 3.2 bwdiff Tab：添加 `gr.DownloadButton`，更新函数 outputs 和返回值
- [x] 3.3 bwgen Tab：添加两个 `gr.DownloadButton`（黑底图、白底图），更新函数 outputs 和返回值
- [x] 3.4 gen-image Tab：添加 `gr.DownloadButton`，更新函数 outputs 和返回值
- [x] 3.5 pipeline Tab：添加三个 `gr.DownloadButton`（黑底图、白底图、结果），更新函数 outputs 和返回值

## 4. 验证

- [x] 4.1 启动 Web UI，逐 Tab 测试处理/生成功能，确认无 Gradio 报错
- [x] 4.2 验证下载按钮触发的是文件下载而非页面跳转
- [x] 4.3 验证下载的 PNG 文件透明区域正常（非白底）
- [x] 4.4 验证 `local/output/rmbg/` 和 `local/output/bwdiff/` 下有自动保存的文件
