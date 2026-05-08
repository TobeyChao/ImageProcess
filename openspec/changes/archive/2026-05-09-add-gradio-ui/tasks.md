## 1. Script refactoring

- [x] 1.1 Refactor `rmbg_process.py`: extract `load_model(model_dir, device)` and `process_image(input_path, model, device, threshold, edge_refine, white_bg)`, guard CLI under `if __name__ == "__main__"`
- [x] 1.2 Refactor `bw_diff.py`: extract `bw_diff(black_path, white_path)` returning PIL Image, guard CLI under `if __name__ == "__main__"`
- [x] 1.3 Refactor `bw_gen.py`: extract `generate_black_white(prompt, ratio, size, output_dir, model)` returning `(black_path, white_path)`, guard CLI under `if __name__ == "__main__"`
- [x] 1.4 Refactor `gen_image.py`: extract `generate_image(prompt, ratio, size, output_dir, model)` returning output path, guard CLI under `if __name__ == "__main__"`
- [x] 1.5 Verify CLI backward compatibility: run each script with test arguments and confirm output matches pre-refactor behavior

## 2. Dependencies and configuration

- [x] 2.1 Create `requirements.txt` with all dependencies (torch, torchvision, transformers, safetensors, pillow, numpy, timm, kornia, google-genai, requests, scipy, gradio, modelscope)
- [x] 2.2 Create `local/config.json` schema with fields: `model_dir`, `gemini_api_key`, `dashscope_api_key`
- [x] 2.3 Ensure `local/config.json` is in `.gitignore`
- [x] 2.4 Update `bwgen` API key resolution: config.json priority > environment variable fallback

## 3. main.py bootstrap script

- [x] 3.1 Create `main.py` with zero external dependencies (stdlib only): python version check, venv detection/creation, dependency import check, model file check
- [x] 3.2 Implement setup wizard as simple HTTP server (`http.server`) with SSE endpoint for log streaming
- [x] 3.3 Implement `POST /api/setup` handler: run `pip install -r requirements.txt` + `modelscope download` via subprocess, stream stdout/stderr line-by-line via SSE
- [x] 3.4 Implement model download progress parsing from `modelscope` output and SSE progress events
- [x] 3.5 Implement post-setup launch: spawn `python app.py --port 7861` as subprocess, forward requests (reverse proxy)
- [x] 3.6 Wire up signal handling: clean shutdown of both main.py and Gradio subprocess on SIGINT/SIGTERM

## 4. Gradio Web UI (app.py)

- [x] 4.1 Create `app.py` with `gr.Blocks` shell, import refactored processing functions from skill scripts
- [x] 4.2 Implement Settings Tab: model dir textbox, Gemini/DashScope API Key password fields, load/save to `local/config.json`
- [x] 4.3 Implement Background Removal Tab: image upload, model dir, threshold slider (0.3-0.7 with labels), edge refine checkbox, white bg checkbox, before/after image display, download button
- [x] 4.4 Implement Black-White Diff Tab: black image upload, white image upload, result display, error handling for size mismatch
- [x] 4.5 Implement Black-White Generate Tab: prompt textbox, ratio dropdown, size dropdown, model dropdown (gemini/wan), black/white result display
- [x] 4.6 Implement Image Generate Tab: prompt textbox, ratio dropdown, size dropdown, model dropdown, result display with download button
- [x] 4.7 Implement Pipeline Tab: prompt + parameters, "One-Click Execute" button, chained bwgen→bwdiff call, display black/white/result three images
- [x] 4.8 Add load/save of Settings values as Gradio State for cross-tab sharing

## 5. Documentation

- [x] 5.1 Update `.claude/CLAUDE.md`: reflect new UI entry point, update directory structure, update download command to ModelScope
- [x] 5.2 Update `.claude/skills/rmbg/references/setup.md`: ModelScope download, add gradio and modelscope to dependency list

## 6. Verification

- [x] 6.1 End-to-end test: `git clone` → `python main.py` → setup wizard → launch → exercise all tabs
- [x] 6.2 Verify backward-compatible CLI: all four scripts accept same args and produce same outputs
- [x] 6.3 Verify `local/config.json` persistence: fill settings → restart → settings pre-filled
