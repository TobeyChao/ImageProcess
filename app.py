"""Image Processing Toolbox — Gradio Web UI."""

import importlib.util
import json
import os
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import gradio as gr

warnings.filterwarnings("ignore", category=FutureWarning, module="timm")

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / ".claude"))

# ── Import skill modules ──────────────────────────────────────────────────────


def _load_module(package, script):
    path = str(PROJECT_DIR / ".claude" / "skills" / package / "scripts" / f"{script}.py")
    spec = importlib.util.spec_from_file_location(script, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[script] = mod
    spec.loader.exec_module(mod)
    return mod


rmbg_mod = _load_module("rmbg", "rmbg_process")
bwdiff_mod = _load_module("bwdiff", "bw_diff")
bwgen_mod = _load_module("bwgen", "bw_gen")
genimg_mod = _load_module("gen-image", "gen_image")

# ── Config helpers ────────────────────────────────────────────────────────────

CONFIG_PATH = PROJECT_DIR / "local" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "model_dir": str(PROJECT_DIR / "local" / "models" / "RMBG-2.0"),
    "gemini_api_key": "",
    "dashscope_api_key": "",
}


def _load_config():
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_config_value(key, env_var=None):
    """Priority: config.json > env var > default."""
    cfg = _load_config()
    if key in cfg and cfg[key]:
        return cfg[key]
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]
    return DEFAULT_CONFIG.get(key, "")


# ── Shared state ──────────────────────────────────────────────────────────────

_loaded_model = None
_loaded_device = None


def get_model(model_dir):
    global _loaded_model, _loaded_device
    if _loaded_model is None:
        _loaded_model, _loaded_device = rmbg_mod.load_model(model_dir)
    return _loaded_model, _loaded_device


def _make_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Tab 1: Settings ───────────────────────────────────────────────────────────

def settings_status():
    """Return status indicators for each field (does not expose key values)."""
    cfg = _load_config()
    gemini_set = bool(cfg.get("gemini_api_key"))
    dashscope_set = bool(cfg.get("dashscope_api_key"))
    return (
        cfg.get("model_dir", DEFAULT_CONFIG["model_dir"]),
        "🔑 已配置" if gemini_set else "❌ 未配置",
        "🔑 已配置" if dashscope_set else "❌ 未配置",
    )


def settings_save(model_dir, gemini_key, dashscope_key):
    cfg = _load_config()
    if model_dir:
        cfg["model_dir"] = model_dir
    if gemini_key.strip():
        cfg["gemini_api_key"] = gemini_key.strip()
    if dashscope_key.strip():
        cfg["dashscope_api_key"] = dashscope_key.strip()
    _save_config(cfg)
    os.makedirs(os.path.join(PROJECT_DIR, "local", "output"), exist_ok=True)
    return "设置已保存 ✓", "🔑 已配置" if (cfg.get("gemini_api_key") or gemini_key.strip()) else "❌ 未配置", "🔑 已配置" if (cfg.get("dashscope_api_key") or dashscope_key.strip()) else "❌ 未配置"


# ── Tab 2: Background Removal (rmbg) ──────────────────────────────────────────

def rmbg_process(image, model_dir, threshold, edge_refine, white_bg):
    if image is None:
        return None, "请上传图片"
    if not model_dir or not os.path.isdir(model_dir):
        return None, "模型目录不存在，请在设置中配置"
    try:
        model, device = get_model(model_dir)
        result = rmbg_mod.process_image(image, model, device,
                                        threshold=threshold,
                                        edge_refine=edge_refine,
                                        white_bg=white_bg)
        return result, "处理完成 ✓"
    except Exception as e:
        return None, f"错误: {e}"


# ── Tab 3: Black-White Diff (bwdiff) ──────────────────────────────────────────

_TMP_BLACK = None
_TMP_WHITE = None


def bwdiff_cache_black(img):
    global _TMP_BLACK
    _TMP_BLACK = img
    return None, None


def bwdiff_cache_white(img):
    global _TMP_WHITE
    _TMP_WHITE = img
    return None, None


def bwdiff_process():
    if _TMP_BLACK is None or _TMP_WHITE is None:
        return None, "请上传黑底图和白底图"
    if _TMP_BLACK.size != _TMP_WHITE.size:
        return None, f"两张图片尺寸不一致（黑底: {_TMP_BLACK.size}，白底: {_TMP_WHITE.size}）"
    try:
        import numpy as np
        from PIL import Image

        black_arr = np.array(_TMP_BLACK.convert("RGB"), dtype=np.float32)
        white_arr = np.array(_TMP_WHITE.convert("RGB"), dtype=np.float32)
        alpha, fg = bwdiff_mod.compute_alpha(black_arr, white_arr)
        result = np.dstack([fg, alpha])
        return Image.fromarray(result, "RGBA"), "处理完成 ✓"
    except Exception as e:
        return None, f"错误: {e}"


# ── Tab 4: Black-White Generate (bwgen) ───────────────────────────────────────

def bwgen_generate(prompt, ratio, size, model):
    if not prompt or not prompt.strip():
        return None, None, "请输入主体描述"

    # Resolve API key from config
    api_key = None
    if model == "wan":
        key = get_config_value("dashscope_api_key", "DASHSCOPE_API_KEY")
        if not key:
            return None, None, "未配置 DashScope API Key，请在设置中填写"
        os.environ["DASHSCOPE_API_KEY"] = key
    else:
        key = get_config_value("gemini_api_key", "GEMINI_API_KEY")
        if not key:
            return None, None, "未配置 Gemini API Key，请在设置中填写"
        os.environ["GEMINI_API_KEY"] = key

    out_dir = str(PROJECT_DIR / "local" / "output" / "bwgen")
    try:
        black_path, white_path = bwgen_mod.generate_black_white(
            prompt.strip(), ratio, size, out_dir, model
        )
        from PIL import Image
        return Image.open(black_path), Image.open(white_path), f"生成完成 ✓\n黑底: {black_path}\n白底: {white_path}"
    except Exception as e:
        return None, None, f"错误: {e}"


# ── Tab 5: Image Generate (gen-image) ────────────────────────────────────────

def genimg_generate(prompt, ratio, size, model):
    if not prompt or not prompt.strip():
        return None, "请输入图像描述"

    if model == "wan":
        key = get_config_value("dashscope_api_key", "DASHSCOPE_API_KEY")
        if not key:
            return None, "未配置 DashScope API Key，请在设置中填写"
        os.environ["DASHSCOPE_API_KEY"] = key
    else:
        key = get_config_value("gemini_api_key", "GEMINI_API_KEY")
        if not key:
            return None, "未配置 Gemini API Key，请在设置中填写"
        os.environ["GEMINI_API_KEY"] = key

    out_dir = str(PROJECT_DIR / "local" / "output" / "gen-image")
    try:
        filepath = genimg_mod.generate_image(prompt.strip(), ratio, size, out_dir, model)
        from PIL import Image
        return Image.open(filepath), f"生成完成 ✓\n{filepath}"
    except Exception as e:
        return None, f"错误: {e}"


# ── Tab 6: Pipeline (bwgen → bwdiff) ─────────────────────────────────────────

def pipeline_run(prompt, ratio, size, model):
    if not prompt or not prompt.strip():
        return None, None, None, "请输入主体描述"

    # Set API key
    if model == "wan":
        key = get_config_value("dashscope_api_key", "DASHSCOPE_API_KEY")
        if not key:
            return None, None, None, "未配置 DashScope API Key"
        os.environ["DASHSCOPE_API_KEY"] = key
    else:
        key = get_config_value("gemini_api_key", "GEMINI_API_KEY")
        if not key:
            return None, None, None, "未配置 Gemini API Key"
        os.environ["GEMINI_API_KEY"] = key

    out_dir = str(PROJECT_DIR / "local" / "output" / "bwgen")
    try:
        black_path, white_path = bwgen_mod.generate_black_white(
            prompt.strip(), ratio, size, out_dir, model
        )
        from PIL import Image
        black_img = Image.open(black_path)
        white_img = Image.open(white_path)

        # bwdiff
        import numpy as np
        black_arr = np.array(black_img.convert("RGB"), dtype=np.float32)
        white_arr = np.array(white_img.convert("RGB"), dtype=np.float32)
        alpha, fg = bwdiff_mod.compute_alpha(black_arr, white_arr)
        result = Image.fromarray(np.dstack([fg, alpha]), "RGBA")

        return black_img, white_img, result, f"管线完成 ✓\n{black_path}\n{white_path}"
    except Exception as e:
        return None, None, None, f"错误: {e}"


# ── Build UI ──────────────────────────────────────────────────────────────────

RATIO_CHOICES = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"]
SIZE_CHOICES = ["512", "1K", "2K", "4K"]
MODEL_CHOICES = ["gemini", "wan"]

CSS = """
#title { text-align: center; font-size: 1.8em; font-weight: 700; padding: 0.5em 0; }
.footer { text-align: center; color: #888; font-size: 0.8em; margin-top: 2em; }
"""

with gr.Blocks(title="Image Processing Toolbox") as app:
    gr.Markdown("# 🖼 Image Processing Toolbox", elem_id="title")

    # Load initial config
    initial_cfg = _load_config()

    with gr.Tab("⚙ 设置"):
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### API 密钥")
                # Compute initial status
                init_model_dir, init_gemini_st, init_dash_st = settings_status()

                with gr.Row():
                    gemini_key = gr.Textbox(
                        label="Gemini API Key",
                        type="password",
                        placeholder="输入新的 API Key（留空不修改）",
                        scale=3,
                    )
                    gemini_status = gr.Textbox(
                        label="状态", value=init_gemini_st, interactive=False, scale=1,
                    )
                with gr.Row():
                    dashscope_key = gr.Textbox(
                        label="DashScope API Key",
                        type="password",
                        placeholder="输入新的 API Key（留空不修改）",
                        scale=3,
                    )
                    dashscope_status = gr.Textbox(
                        label="状态", value=init_dash_st, interactive=False, scale=1,
                    )

                gr.Markdown("### 模型路径")
                model_dir_input = gr.Textbox(
                    label="模型目录",
                    value=initial_cfg.get("model_dir", DEFAULT_CONFIG["model_dir"]),
                    placeholder="BiRefNet 模型目录路径",
                )
                save_btn = gr.Button("💾 保存设置", variant="primary", size="lg")
                save_status = gr.Textbox(label="状态", interactive=False)

            with gr.Column(scale=1):
                gr.Markdown("""
                ### 说明
                - **Gemini API Key**: 用于 Gemini 图片生成（gen-image、bwgen）
                - **DashScope API Key**: 用于阿里云百炼 Wan2.7 Pro 图片生成
                - **模型目录**: BiRefNet 深度学习去背景模型所在目录
                - API Key 已配置时显示「🔑 已配置」，无需重复填写
                - 配置保存到 `local/config.json`，下次自动加载
                """)

        save_btn.click(
            fn=settings_save,
            inputs=[model_dir_input, gemini_key, dashscope_key],
            outputs=[save_status, gemini_status, dashscope_status],
        )

    with gr.Tab("🎯 去背景"):
        gr.Markdown("### BiRefNet 深度学习去背景")
        with gr.Row():
            with gr.Column(scale=1):
                rmbg_input = gr.Image(label="上传图片", type="pil", height=300)
                rmbg_model_dir = gr.Textbox(
                    label="模型目录",
                    value=initial_cfg.get("model_dir", DEFAULT_CONFIG["model_dir"]),
                )
                with gr.Row():
                    rmbg_threshold = gr.Slider(
                        label="二值化阈值",
                        minimum=0.3, maximum=0.7, value=0.5, step=0.05,
                        info="低：保留更多发丝细节 | 高：边缘更干净",
                    )
                with gr.Row():
                    rmbg_edge = gr.Checkbox(label="边缘优化", value=True)
                    rmbg_whitebg = gr.Checkbox(label="白底输出", value=False)
                rmbg_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
            with gr.Column(scale=1):
                rmbg_output = gr.Image(label="结果", type="pil", height=300, format="png", image_mode="RGBA", buttons=["fullscreen"])
                rmbg_status = gr.Textbox(label="状态", interactive=False)

        rmbg_btn.click(
            fn=rmbg_process,
            inputs=[rmbg_input, rmbg_model_dir, rmbg_threshold, rmbg_edge, rmbg_whitebg],
            outputs=[rmbg_output, rmbg_status],
        )

    with gr.Tab("⬛⬜ 黑白差分"):
        gr.Markdown("### 黑白差分去背景（需同机位黑底+白底图）")
        with gr.Row():
            with gr.Column(scale=1):
                bwdiff_black = gr.Image(label="黑底图", type="pil", height=250)
            with gr.Column(scale=1):
                bwdiff_white = gr.Image(label="白底图", type="pil", height=250)
            with gr.Column(scale=1):
                bwdiff_result = gr.Image(label="抠图结果", type="pil", height=250, format="png", image_mode="RGBA", buttons=["fullscreen"])
        with gr.Row():
            bwdiff_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
        bwdiff_status = gr.Textbox(label="状态", interactive=False)

        bwdiff_black.upload(fn=bwdiff_cache_black, inputs=[bwdiff_black], outputs=[])
        bwdiff_white.upload(fn=bwdiff_cache_white, inputs=[bwdiff_white], outputs=[])
        bwdiff_btn.click(
            fn=bwdiff_process, inputs=[], outputs=[bwdiff_result, bwdiff_status]
        )

    with gr.Tab("🎨 生黑白底图"):
        gr.Markdown("### 从描述生成黑白背景双图")
        with gr.Row():
            with gr.Column(scale=1):
                bwgen_prompt = gr.Textbox(
                    label="主体描述",
                    placeholder="例如：一把发光的剑",
                    lines=2,
                )
                with gr.Row():
                    bwgen_ratio = gr.Dropdown(
                        label="宽高比", choices=RATIO_CHOICES, value="1:1",
                    )
                    bwgen_size = gr.Dropdown(
                        label="分辨率", choices=SIZE_CHOICES, value="1K",
                    )
                    bwgen_model = gr.Dropdown(
                        label="模型", choices=MODEL_CHOICES, value="gemini",
                    )
                bwgen_btn = gr.Button("▶ 开始生成", variant="primary", size="lg")
            with gr.Column(scale=1):
                bwgen_black = gr.Image(label="黑底图", type="pil", height=250, format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                bwgen_white = gr.Image(label="白底图", type="pil", height=250, format="png", buttons=["fullscreen"])
        bwgen_status = gr.Textbox(label="状态", interactive=False)

        bwgen_btn.click(
            fn=bwgen_generate,
            inputs=[bwgen_prompt, bwgen_ratio, bwgen_size, bwgen_model],
            outputs=[bwgen_black, bwgen_white, bwgen_status],
        )

    with gr.Tab("🖼 生图"):
        gr.Markdown("### AI 图片生成")
        with gr.Row():
            with gr.Column(scale=1):
                genimg_prompt = gr.Textbox(
                    label="提示词（英文效果更佳）",
                    placeholder="例如：a cute orange tabby cat",
                    lines=2,
                )
                with gr.Row():
                    genimg_ratio = gr.Dropdown(
                        label="宽高比", choices=RATIO_CHOICES, value="1:1",
                    )
                    genimg_size = gr.Dropdown(
                        label="分辨率", choices=SIZE_CHOICES, value="1K",
                    )
                    genimg_model = gr.Dropdown(
                        label="模型", choices=MODEL_CHOICES, value="gemini",
                    )
                genimg_btn = gr.Button("▶ 开始生成", variant="primary", size="lg")
            with gr.Column(scale=1):
                genimg_output = gr.Image(label="生成结果", type="pil", height=350, format="png", buttons=["fullscreen"])
        genimg_status = gr.Textbox(label="状态", interactive=False)

        genimg_btn.click(
            fn=genimg_generate,
            inputs=[genimg_prompt, genimg_ratio, genimg_size, genimg_model],
            outputs=[genimg_output, genimg_status],
        )

    with gr.Tab("🔄 一键管线"):
        gr.Markdown("### bwgen → bwdiff 一键抠图")
        with gr.Row():
            with gr.Column(scale=1):
                pipe_prompt = gr.Textbox(
                    label="主体描述",
                    placeholder="例如：一把发光的剑",
                    lines=2,
                )
                with gr.Row():
                    pipe_ratio = gr.Dropdown(
                        label="宽高比", choices=RATIO_CHOICES, value="1:1",
                    )
                    pipe_size = gr.Dropdown(
                        label="分辨率", choices=SIZE_CHOICES, value="1K",
                    )
                    pipe_model = gr.Dropdown(
                        label="模型", choices=MODEL_CHOICES, value="gemini",
                    )
                pipe_btn = gr.Button("▶ 一键执行", variant="primary", size="lg")
            with gr.Column(scale=1):
                pipe_black = gr.Image(label="黑底图", type="pil", height=200, format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                pipe_white = gr.Image(label="白底图", type="pil", height=200, format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                pipe_result = gr.Image(label="抠图结果", type="pil", height=200, format="png", image_mode="RGBA", buttons=["fullscreen"])
        pipe_status = gr.Textbox(label="状态", interactive=False)

        pipe_btn.click(
            fn=pipeline_run,
            inputs=[pipe_prompt, pipe_ratio, pipe_size, pipe_model],
            outputs=[pipe_black, pipe_white, pipe_result, pipe_status],
        )

    gr.Markdown(
        "Made with Gradio | 所有处理在本地执行，图片不会上传到任何服务器",
        elem_classes="footer",
    )


if __name__ == "__main__":
    # Create output directories
    for sub in ["rmbg", "bwdiff", "bwgen", "gen-image"]:
        os.makedirs(PROJECT_DIR / "local" / "output" / sub, exist_ok=True)

    app.launch(server_name="127.0.0.1", server_port=7861, share=False, css=CSS, theme=gr.themes.Soft())
