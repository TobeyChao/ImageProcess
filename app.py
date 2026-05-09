"""Image Processing Toolbox — Gradio Web UI."""

import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

import gradio as gr

warnings.filterwarnings("ignore", category=FutureWarning, module="timm")

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from core import api_keys, config as cfg_mod, errors, skills, state

# Skill modules (lazy-loaded; calling skills.load() the first time loads them)
rmbg_mod = skills.load("rmbg")
bwdiff_mod = skills.load("bwdiff")
bwgen_mod = skills.load("bwgen")
genimg_mod = skills.load("gen-image")

# ── Config helpers ────────────────────────────────────────────────────────────

CONFIG_PATH = PROJECT_DIR / "local" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL_DIR = str(PROJECT_DIR / "local" / "models" / "RMBG-2.0")


def _load_config():
    return cfg_mod.load(CONFIG_PATH)


def _save_config(data):
    cfg_mod.save(CONFIG_PATH, data)


def get_config_value(key, env_var=None):
    return cfg_mod.get_value(CONFIG_PATH, key, env_var=env_var,
                             default=cfg_mod.DEFAULTS.get(key, ""))


# ── Shared state ──────────────────────────────────────────────────────────────


def get_model(model_dir):
    return state.registry.get_or_load(
        f"rmbg::{model_dir}",
        rmbg_mod.load_model,
        model_dir=model_dir,
    )


def _make_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Tab 1: Settings ───────────────────────────────────────────────────────────

def settings_status():
    """Return status indicators for each field (does not expose key values)."""
    cfg = _load_config()
    gemini_set = bool(cfg.get("gemini_api_key"))
    dashscope_set = bool(cfg.get("dashscope_api_key"))
    return (
        cfg.get("model_dir", DEFAULT_MODEL_DIR),
        "🔑 已配置" if gemini_set else "❌ 未配置",
        "🔑 已配置" if dashscope_set else "❌ 未配置",
    )


def _gpu_status():
    """Return (status_text, install_cmd, show_install) for the settings GPU section."""
    import subprocess, re, sys, platform
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        mps_ok = (
            getattr(torch.backends, "mps", None) is not None
            and torch.backends.mps.is_available()
        )
        torch_ver = torch.__version__
        gpu_name = torch.cuda.get_device_name(0) if cuda_ok else ""
    except ImportError:
        return "❌ torch 未安装", "", False

    # Apple Silicon path — MPS ships with stock macOS arm64 wheels, no special install
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        chip = platform.processor() or "arm64"
        if mps_ok:
            return f"✅ Apple Silicon ({chip}) · MPS 已启用 ({torch_ver})", "", False
        return (
            f"⚠️ Apple Silicon ({chip}) · MPS 不可用 ({torch_ver})  →  请确认 torch 为 macOS arm64 版本",
            "",
            False,
        )

    if not gpu_name:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                gpu_name = r.stdout.strip().split("\n")[0].strip()
        except Exception:
            pass

    if cuda_ok:
        return f"✅ {gpu_name} · CUDA 已启用 ({torch_ver})", "", False
    elif gpu_name:
        cuda_url = "cu128"
        try:
            r = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
            m = re.search(r"CUDA Version:\s*(\d+)", r.stdout)
            if m:
                major = int(m.group(1))
                if major < 12:
                    cuda_url = "cu118"
                elif major < 13:
                    cuda_url = "cu128"
        except Exception:
            pass
        # Use the venv pip directly — no activation needed, avoids "from versions: none"
        pip = str(PROJECT_DIR / (".venv/Scripts/pip.exe" if sys.platform == "win32" else ".venv/bin/pip"))
        cmd = f'{pip} install torch torchvision --force-reinstall --index-url https://download.pytorch.org/whl/{cuda_url}'
        return (
            f"⚠️ {gpu_name} · 未启用 CUDA ({torch_ver})  →  退出应用，执行下方命令后重启",
            cmd,
            True,
        )
    else:
        return f"💻 未检测到 NVIDIA GPU，使用 CPU 推理 ({torch_ver})", "", False


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
    return (
        "设置已保存 ✓",
        "🔑 已配置" if (cfg.get("gemini_api_key") or gemini_key.strip()) else "❌ 未配置",
        "🔑 已配置" if (cfg.get("dashscope_api_key") or dashscope_key.strip()) else "❌ 未配置",
    )


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
        msg, hint = errors.user_message(e)
        return None, f"{msg}\n{hint}"


# ── Tab 3: Black-White Diff (bwdiff) ──────────────────────────────────────────


def bwdiff_process(black, white):
    """Take both PIL inputs directly (no module-level state)."""
    if black is None or white is None:
        return None, "请上传黑底图和白底图"
    if black.size != white.size:
        return None, f"两张图片尺寸不一致（黑底: {black.size}，白底: {white.size}）"
    try:
        import numpy as np
        from PIL import Image

        black_arr = np.array(black.convert("RGB"), dtype=np.float32)
        white_arr = np.array(white.convert("RGB"), dtype=np.float32)
        alpha, fg = bwdiff_mod.compute_alpha(black_arr, white_arr)
        result = np.dstack([fg, alpha])
        return Image.fromarray(result, "RGBA"), "处理完成 ✓"
    except Exception as e:
        msg, hint = errors.user_message(e)
        return None, f"{msg}\n{hint}"


# ── Tab 4: Black-White Generate (bwgen) ───────────────────────────────────────

def bwgen_generate(prompt, ratio, size, model):
    if not prompt or not prompt.strip():
        return None, None, "请输入主体描述"

    out_dir = str(PROJECT_DIR / "local" / "output" / "bwgen")
    try:
        with api_keys.use_api_key(CONFIG_PATH, model):
            black_path, white_path = bwgen_mod.generate_black_white(
                prompt.strip(), ratio, size, out_dir, model
            )
        from PIL import Image
        return (Image.open(black_path), Image.open(white_path),
                f"生成完成 ✓\n黑底: {black_path}\n白底: {white_path}")
    except api_keys.MissingKey as e:
        return None, None, str(e)
    except Exception as e:
        msg, hint = errors.user_message(e)
        return None, None, f"{msg}\n{hint}"


# ── Tab 5: Image Generate (gen-image) ────────────────────────────────────────

def genimg_generate(prompt, ratio, size, model):
    if not prompt or not prompt.strip():
        return None, "请输入图像描述"

    out_dir = str(PROJECT_DIR / "local" / "output" / "gen-image")
    try:
        with api_keys.use_api_key(CONFIG_PATH, model):
            filepath = genimg_mod.generate_image(prompt.strip(), ratio, size, out_dir, model)
        from PIL import Image
        return Image.open(filepath), f"生成完成 ✓\n{filepath}"
    except api_keys.MissingKey as e:
        return None, str(e)
    except Exception as e:
        msg, hint = errors.user_message(e)
        return None, f"{msg}\n{hint}"


# ── Tab 6: Pipeline (bwgen → bwdiff) ─────────────────────────────────────────

def pipeline_run(prompt, ratio, size, model):
    if not prompt or not prompt.strip():
        return None, None, None, "请输入主体描述"

    out_dir = str(PROJECT_DIR / "local" / "output" / "bwgen")
    try:
        # Step 1: generate black + white background pair (reuses bwgen module)
        with api_keys.use_api_key(CONFIG_PATH, model):
            black_path, white_path = bwgen_mod.generate_black_white(
                prompt.strip(), ratio, size, out_dir, model
            )

        # Step 2: diff to RGBA (reuses bwdiff module — no code duplication)
        result = bwdiff_mod.bw_diff(black_path, white_path)

        from PIL import Image
        return (Image.open(black_path), Image.open(white_path), result,
                f"管线完成 ✓\n{black_path}\n{white_path}")
    except api_keys.MissingKey as e:
        return None, None, None, str(e)
    except Exception as e:
        msg, hint = errors.user_message(e)
        return None, None, None, f"{msg}\n{hint}"


# ── Build UI ──────────────────────────────────────────────────────────────────

RATIO_CHOICES = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"]
SIZE_CHOICES = ["512", "1K", "2K", "4K"]
MODEL_CHOICES = ["gemini", "wan"]

EYE_TOGGLE_JS = """
<script>
(function(){
var EYE='<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\"/><circle cx=\"12\" cy=\"12\" r=\"3\"/></svg>';
var EYE_OFF='<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24\"/><line x1=\"1\" y1=\"1\" x2=\"23\" y2=\"23\"/></svg>';

function addEye(id){
  var el=document.getElementById(id);
  if(!el) return false;
  var inp=el.querySelector('input');
  if(!inp) return false;
  var wrap=inp.parentElement;
  if(!wrap) return false;
  if(wrap.querySelector('.pw-eye')) return true;
  wrap.style.position='relative';
  var btn=document.createElement('button');
  btn.className='pw-eye'; btn.type='button'; btn.innerHTML=EYE;
  btn.onclick=function(e){
    e.preventDefault(); e.stopPropagation();
    if(inp.type==='password'){ inp.type='text'; btn.innerHTML=EYE_OFF; btn.classList.add('active'); }
    else{ inp.type='password'; btn.innerHTML=EYE; btn.classList.remove('active'); }
  };
  wrap.appendChild(btn);
  return true;
}
function init(){
  addEye('gemini-key-input');
  addEye('dashscope-key-input');
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
else init();
var mo=new MutationObserver(function(){
  if(addEye('gemini-key-input') && addEye('dashscope-key-input')) mo.disconnect();
});
mo.observe(document.body,{childList:true,subtree:true});
})();
</script>
"""

CSS = """
html { scrollbar-gutter: stable; }
#title { text-align: center; font-size: 1.8em; font-weight: 700; padding: 0.5em 0; }
.footer { text-align: center; color: #888; font-size: 0.8em; margin-top: 2em; }
.alpha-preview img {
    background-color: #fff;
    background-image: linear-gradient(45deg, #bbb 25%, transparent 25%),
                      linear-gradient(-45deg, #bbb 25%, transparent 25%),
                      linear-gradient(45deg, transparent 75%, #bbb 75%),
                      linear-gradient(-45deg, transparent 75%, #bbb 75%);
    background-size: 16px 16px;
    background-position: 0 0, 0 8px, 8px -8px, -8px 0px;
}
#gemini-key-input input, #dashscope-key-input input { padding-right: 32px !important; }
.pw-eye {
    position: absolute; right: 2px; top: 50%; transform: translateY(-50%);
    width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
    background: transparent; border: none; cursor: pointer;
    color: inherit; opacity: 0.4; z-index: 10;
    border-radius: 4px; padding: 0;
}
.pw-eye:hover { opacity: 0.7; }
.pw-eye.active { opacity: 0.7; }
"""

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

with gr.Blocks(title="Image Processing Toolbox") as app:
    gr.Markdown("# 🔧 Image Processing Toolbox", elem_id="title")

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
                        value=initial_cfg.get("gemini_api_key", ""),
                        placeholder="输入 API Key",
                        scale=3,
                        elem_id="gemini-key-input",
                    )
                    gemini_status = gr.Textbox(
                        label="状态", value=init_gemini_st, interactive=False, scale=1,
                    )
                with gr.Row():
                    dashscope_key = gr.Textbox(
                        label="DashScope API Key",
                        type="password",
                        value=initial_cfg.get("dashscope_api_key", ""),
                        placeholder="输入 API Key",
                        scale=3,
                        elem_id="dashscope-key-input",
                    )
                    dashscope_status = gr.Textbox(
                        label="状态", value=init_dash_st, interactive=False, scale=1,
                    )

                gr.Markdown("### 模型路径")
                model_dir_input = gr.Textbox(
                    label="模型目录",
                    value=initial_cfg.get("model_dir", DEFAULT_MODEL_DIR),
                    placeholder="BiRefNet 模型目录路径",
                )
                save_btn = gr.Button("💾 保存设置", variant="primary", size="lg")
                save_status = gr.Textbox(label="状态", interactive=False)

                gr.Markdown("### GPU 加速")
                init_gpu_st, init_gpu_cmd, init_gpu_vis = _gpu_status()
                with gr.Row():
                    gpu_status_box = gr.Textbox(
                        label="当前状态", value=init_gpu_st, interactive=False, scale=4,
                    )
                    gpu_refresh_btn = gr.Button("🔄 刷新", scale=1, size="sm")
                gpu_install_box = gr.Textbox(
                    label="安装命令（退出应用后在项目 .venv 中执行，完成后重新启动）",
                    value=init_gpu_cmd, interactive=False, visible=init_gpu_vis,
                )

            with gr.Column(scale=1):
                gr.Markdown("""
                ### 说明
                - **Gemini API Key**: 用于 Gemini 图片生成（gen-image、bwgen）
                - **DashScope API Key**: 用于阿里云百炼 Wan2.7 Pro 图片生成
                - **模型目录**: BiRefNet 深度学习去背景模型所在目录
                - 已配置的 Key 会自动填入（密码遮罩），点击 👁 可查看明文
                - 输入新 Key 即可替换，留空不修改已有配置
                - 配置保存到 `local/config.json`，下次自动加载
                """)

        save_btn.click(
            fn=settings_save,
            inputs=[model_dir_input, gemini_key, dashscope_key],
            outputs=[save_status, gemini_status, dashscope_status],
        )
        gpu_refresh_btn.click(
            fn=lambda: (lambda st, cmd, vis: (st, gr.update(value=cmd, visible=vis)))(*_gpu_status()),
            outputs=[gpu_status_box, gpu_install_box],
        )

    with gr.Tab("🎯 去背景"):
        gr.Markdown("### BiRefNet 深度学习去背景")
        with gr.Row():
            with gr.Column(scale=1):
                rmbg_input = gr.Image(label="上传图片", type="pil", height="45vh")
                rmbg_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
                with gr.Accordion("⚙ 高级选项", open=False):
                    rmbg_model_dir = gr.Textbox(
                        label="模型目录",
                        value=initial_cfg.get("model_dir", DEFAULT_MODEL_DIR),
                        info="BiRefNet 模型文件目录，通常无需修改",
                    )
                    rmbg_threshold = gr.Slider(
                        label="二值化阈值",
                        minimum=0.3, maximum=0.7, value=0.5, step=0.05,
                        info="0.3–0.4 保留发丝细节；0.5 平衡；0.6–0.7 边缘更干净",
                    )
                    with gr.Row():
                        rmbg_edge = gr.Checkbox(label="边缘优化", value=True,
                                                info="高斯平滑 mask 边缘，去锯齿，处理时间约增加 10%")
                        rmbg_whitebg = gr.Checkbox(label="白底输出", value=False,
                                                   info="输出白色背景 RGB 图而非透明 PNG，适合直接打印")
            with gr.Column(scale=1):
                rmbg_output = gr.Image(label="结果", type="pil", height="45vh",
                                       format="png", image_mode="RGBA", buttons=["fullscreen"],
                                       elem_classes=["alpha-preview"])
                rmbg_status = gr.Textbox(label="状态", interactive=False, lines=1)
        rmbg_msg_state = gr.State("")

        rmbg_btn.click(
            fn=lambda: "处理中...",
            outputs=[rmbg_status],
        ).then(
            fn=rmbg_process,
            inputs=[rmbg_input, rmbg_model_dir, rmbg_threshold, rmbg_edge, rmbg_whitebg],
            outputs=[rmbg_output, rmbg_msg_state],
        ).then(
            fn=lambda s: s,
            inputs=[rmbg_msg_state],
            outputs=[rmbg_status],
        )

    with gr.Tab("⬛⬜ 黑白差分"):
        gr.Markdown("### 黑白差分去背景（需同机位黑底+白底图）")
        with gr.Row():
            with gr.Column(scale=1):
                bwdiff_black = gr.Image(label="黑底图", type="pil", height="35vh")
            with gr.Column(scale=1):
                bwdiff_white = gr.Image(label="白底图", type="pil", height="35vh")
            with gr.Column(scale=1):
                bwdiff_result = gr.Image(label="抠图结果", type="pil", height="35vh",
                                        format="png", image_mode="RGBA", buttons=["fullscreen"],
                                        elem_classes=["alpha-preview"])
        with gr.Row():
            bwdiff_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
        bwdiff_status = gr.Textbox(label="状态", interactive=False, lines=1)

        bwdiff_btn.click(
            fn=bwdiff_process,
            inputs=[bwdiff_black, bwdiff_white],
            outputs=[bwdiff_result, bwdiff_status],
        )

    with gr.Tab("🎨 生黑白底图"):
        gr.Markdown("### 从描述生成黑白背景双图")
        with gr.Row():
            with gr.Column(scale=1):
                bwgen_prompt = gr.Textbox(
                    label="主体描述",
                    placeholder="例如：一把发光的魔法剑、一只蓬松的白猫",
                    lines=2,
                    info="描述主体即可，无需提到背景。系统自动添加黑/白背景指令。",
                )
                with gr.Row():
                    bwgen_ratio = gr.Dropdown(
                        label="宽高比", choices=RATIO_CHOICES, value="1:1",
                        info="1:1 通用；16:9 横屏壁纸；9:16 手机壁纸",
                    )
                    bwgen_size = gr.Dropdown(
                        label="分辨率", choices=SIZE_CHOICES, value="1K",
                        info="1K=1024px；2K=2048px；4K 仅 Wan2.7 支持",
                    )
                    bwgen_model = gr.Dropdown(
                        label="模型", choices=MODEL_CHOICES, value="gemini",
                        info="Gemini 速度快；Wan2.7 质量更高、支持 4K",
                    )
                bwgen_btn = gr.Button("▶ 开始生成", variant="primary", size="lg")
            with gr.Column(scale=1):
                bwgen_black = gr.Image(label="黑底图", type="pil", height="38vh",
                                      format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                bwgen_white = gr.Image(label="白底图", type="pil", height="38vh",
                                      format="png", buttons=["fullscreen"])
        bwgen_status = gr.Textbox(label="状态", interactive=False, lines=2)

        bwgen_btn.click(
            fn=bwgen_generate,
            inputs=[bwgen_prompt, bwgen_ratio, bwgen_size, bwgen_model],
            outputs=[bwgen_black, bwgen_white, bwgen_status],
        )

    with gr.Tab("📷 生图"):
        gr.Markdown("### AI 图片生成")
        with gr.Row():
            with gr.Column(scale=1):
                genimg_prompt = gr.Textbox(
                    label="提示词（英文效果更佳）",
                    placeholder="例如：a glowing magic sword on black background, fantasy art style",
                    lines=2,
                    info="描述主体、风格、氛围；英文提示词效果通常优于中文。",
                )
                with gr.Row():
                    genimg_ratio = gr.Dropdown(
                        label="宽高比", choices=RATIO_CHOICES, value="1:1",
                        info="1:1 通用；16:9 横屏壁纸；9:16 手机壁纸",
                    )
                    genimg_size = gr.Dropdown(
                        label="分辨率", choices=SIZE_CHOICES, value="1K",
                        info="1K=1024px；2K=2048px；4K 仅文生图模式支持",
                    )
                    genimg_model = gr.Dropdown(
                        label="模型", choices=MODEL_CHOICES, value="gemini",
                        info="Gemini 速度快；Wan2.7 质量更高、支持 4K",
                    )
                genimg_btn = gr.Button("▶ 开始生成", variant="primary", size="lg")
            with gr.Column(scale=1):
                genimg_output = gr.Image(label="生成结果", type="pil", height="50vh",
                                        format="png", buttons=["fullscreen"])
        genimg_status = gr.Textbox(label="状态", interactive=False, lines=2)

        genimg_btn.click(
            fn=genimg_generate,
            inputs=[genimg_prompt, genimg_ratio, genimg_size, genimg_model],
            outputs=[genimg_output, genimg_status],
        )

    with gr.Tab("🔄 一键管线"):
        gr.Markdown("### bwgen → bwdiff 一键抠图")

        with gr.Row():
            with gr.Column(scale=2):
                pipe_prompt = gr.Textbox(
                    label="主体描述",
                    placeholder="例如：一把发光的剑",
                    lines=2,
                    info="描述主体即可，系统自动生成黑底图和白底图后完成抠图。",
                )
                with gr.Row():
                    pipe_ratio = gr.Dropdown(
                        label="宽高比", choices=RATIO_CHOICES, value="1:1",
                        info="1:1 通用；16:9 横屏壁纸；9:16 手机壁纸",
                    )
                    pipe_size = gr.Dropdown(
                        label="分辨率", choices=SIZE_CHOICES, value="1K",
                        info="1K=1024px；2K=2048px；4K 仅 Wan2.7 支持",
                    )
                    pipe_model = gr.Dropdown(
                        label="模型", choices=MODEL_CHOICES, value="gemini",
                        info="Gemini 速度快；Wan2.7 质量更高、支持 4K",
                    )
                pipe_btn = gr.Button("▶ 一键执行", variant="primary", size="lg")
            with gr.Column(scale=1):
                gr.Markdown("""
**流程说明**
1. 根据描述生成黑底 + 白底图（bwgen）
2. 黑白差分计算 alpha 通道（bwdiff）
3. 输出带透明通道的 PNG

适合：快速从文字描述得到带透明背景的素材。
""")

        with gr.Row():
            with gr.Column(scale=1):
                pipe_black = gr.Image(label="黑底图", type="pil", height="35vh",
                                     format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                pipe_white = gr.Image(label="白底图", type="pil", height="35vh",
                                     format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                pipe_result = gr.Image(label="抠图结果", type="pil", height="35vh",
                                      format="png", image_mode="RGBA", buttons=["fullscreen"],
                                      elem_classes=["alpha-preview"])

        pipe_status = gr.Textbox(label="状态", interactive=False, lines=2)

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

    app.launch(server_name="127.0.0.1", server_port=7861, share=False, css=CSS, theme=THEME, head=EYE_TOGGLE_JS)
