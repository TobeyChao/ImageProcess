## 1. Refactor rmbg_process.py model loading

- [x] 1.1 Replace manual importlib model loading with `AutoModelForImageSegmentation.from_pretrained(model_dir, trust_remote_code=True, local_files_only=True)`
- [x] 1.2 Remove unused imports (importlib.util, types) after refactoring
- [x] 1.3 Remove virtual package creation code (`_rmbg_model` package + `sys.path.insert`)
- [x] 1.4 Simplify device auto-detection logic if `from_pretrained` handles it, keeping the GPU→CPU fallback

## 2. Refactor rmbg_process.py image processing

- [x] 2.1 Simplify model output extraction to match official demo pattern (`preds[-1].sigmoid().cpu()`)
- [x] 2.2 Remove list/tuple/dim branching logic in output handling
- [x] 2.3 Comment out threshold binarization code — use raw sigmoid output directly as continuous alpha channel
- [x] 2.4 Comment out edge_refine code path, function signature keeps the param but defaults to False
- [x] 2.5 Comment out white_bg code path, function signature keeps the param but defaults to False

## 3. Update app.py rmbg Tab

- [x] 3.1 Comment out advanced option controls: rmbg_threshold slider, rmbg_edge checkbox, rmbg_whitebg checkbox and their gr.Row wrappers
- [x] 3.2 Comment out advanced inputs from `rmbg_btn.click()` chain, pass default values directly

## 4. Verify

- [x] 4.1 Run existing pytest suite to confirm no regressions (55 passed)
- [x] 4.2 Verify CLI mode still works: module imports OK, signatures correct
