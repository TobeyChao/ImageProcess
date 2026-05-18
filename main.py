#!/usr/bin/env python3
"""Image Processing Toolbox — zero-dependency bootstrap launcher.

Usage:
    python main.py

This script uses only Python stdlib so the user can run it immediately after
git clone, without any pip install.
"""

import os
import subprocess
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

# ROCm on Windows wheel URLs (Python 3.12 required; distinct from Linux rocm index)
ROCM_WIN_VERSION = "7.2.1"
ROCM_WIN_TORCH_VER = "2.9.1"
ROCM_WIN_TORCHVISION_VER = "0.24.1"
ROCM_WIN_TORCHAUDIO_VER = "2.9.1"
ROCM_WIN_BASE_URL = f"https://repo.radeon.com/rocm/windows/rocm-rel-{ROCM_WIN_VERSION}"
ROCM_WIN_SDK_WHEELS = [
    f"{ROCM_WIN_BASE_URL}/rocm_sdk_core-{ROCM_WIN_VERSION}-py3-none-win_amd64.whl",
    f"{ROCM_WIN_BASE_URL}/rocm_sdk_devel-{ROCM_WIN_VERSION}-py3-none-win_amd64.whl",
    f"{ROCM_WIN_BASE_URL}/rocm_sdk_libraries_custom-{ROCM_WIN_VERSION}-py3-none-win_amd64.whl",
    f"{ROCM_WIN_BASE_URL}/rocm-{ROCM_WIN_VERSION}.tar.gz",
]
ROCM_WIN_TORCH_WHEELS = [
    f"{ROCM_WIN_BASE_URL}/torch-{ROCM_WIN_TORCH_VER}%2Brocm{ROCM_WIN_VERSION}-cp312-cp312-win_amd64.whl",
    f"{ROCM_WIN_BASE_URL}/torchvision-{ROCM_WIN_TORCHVISION_VER}%2Brocm{ROCM_WIN_VERSION}-cp312-cp312-win_amd64.whl",
    f"{ROCM_WIN_BASE_URL}/torchaudio-{ROCM_WIN_TORCHAUDIO_VER}%2Brocm{ROCM_WIN_VERSION}-cp312-cp312-win_amd64.whl",
]

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
VENV_PYTHON = (
    VENV_DIR / "Scripts" / "python.exe" if sys.platform == "win32"
    else VENV_DIR / "bin" / "python"
)
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
MODEL_DIR = PROJECT_DIR / "local" / "models" / "RMBG-2.0"
MODEL_KEY_FILE = MODEL_DIR / "model.safetensors"

# (display_name, import_name) — for packages where pip name ≠ import name
REQUIRED_DEPS = [
    ("gradio", "gradio"),
    ("torch", "torch"),
    ("torchvision", "torchvision"),
    ("transformers", "transformers"),
    ("safetensors", "safetensors"),
    ("pillow", "PIL"),
    ("numpy", "numpy"),
    ("timm", "timm"),
    ("kornia", "kornia"),
    ("google-genai", "google.genai"),
    ("requests", "requests"),
    ("scipy", "scipy"),
    ("modelscope", "modelscope"),
]


# ── Environment checks (unchanged from original) ────────────────────────────────

def check_python():
    """Return (ok, version_str)."""
    v = sys.version_info
    ok = v >= (3, 10)
    return ok, f"{v.major}.{v.minor}.{v.micro}"


def check_venv():
    """Return (ok, path)."""
    ok = VENV_PYTHON.is_file()
    return ok, str(VENV_DIR)


def check_deps():
    """Return list of missing dependency display names (checks inside .venv)."""
    if not VENV_PYTHON.is_file():
        return [d[0] for d in REQUIRED_DEPS]
    # Fast path: test all imports in a single subprocess call (avoids 13× startup cost)
    names = [import_name for _, import_name in REQUIRED_DEPS]
    script = (
        "import sys; "
        "[__import__(n) for n in " + str(names) + "]; "
        "print('ok')"
    )
    result = subprocess.run(
        [str(VENV_PYTHON), "-c", script],
        capture_output=True, text=True,
    )
    if result.stdout.strip() == "ok":
        return []
    # Slow path: identify which ones are missing (rare — only when a dep is broken)
    missing = []
    for display_name, import_name in REQUIRED_DEPS:
        r = subprocess.run(
            [str(VENV_PYTHON), "-c", f"import {import_name}"],
            capture_output=True,
        )
        if r.returncode != 0:
            missing.append(display_name)
    return missing


def check_model():
    """Return (ok, path)."""
    ok = MODEL_KEY_FILE.is_file()
    return ok, str(MODEL_DIR)


def _detect_amd_gpu():
    """Return AMD GPU display name on Windows/Linux, or empty string."""
    import platform
    if platform.system() == "Windows":
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController | "
                 "Where-Object { $_.Name -match 'AMD|Radeon' } | "
                 "Select-Object -First 1).Name"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return ""
    if platform.system() == "Linux":
        try:
            r = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.splitlines():
                low = line.lower()
                if ("vga" in low or "display" in low) and ("amd" in low or "radeon" in low):
                    return line.split(":", 2)[-1].strip() if line.count(":") >= 2 else line.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
    return ""


def check_gpu():
    """Return dict describing GPU support.

    Keys:
      backend: 'cuda' | 'rocm' | 'mps' | 'cpu'
      has_nvidia (bool), cuda_ok (bool): NVIDIA / CUDA path
      has_amd (bool), rocm_ok (bool): AMD / ROCm path
      is_apple_silicon (bool), mps_ok (bool): Apple Silicon path
      name (str): displayable GPU name
      cuda_index_url (str): PyTorch wheel index suffix for CUDA install
      rocm_index_url (str): PyTorch wheel index suffix for ROCm install
    """
    import re
    import platform

    is_windows = platform.system() == "Windows"

    info = {
        "backend": "cpu",
        "has_nvidia": False,
        "cuda_ok": False,
        "has_amd": False,
        "rocm_ok": False,
        "is_apple_silicon": False,
        "mps_ok": False,
        "name": "",
        "cuda_index_url": "cu128",
        "rocm_index_url": "rocm6.4",
        "rocm_windows": False,
        "rocm_python_ok": True,
    }

    # Apple Silicon detection (no external tools needed)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        info["is_apple_silicon"] = True
        info["name"] = f"Apple Silicon ({platform.processor() or 'arm64'})"
        if VENV_PYTHON.is_file():
            r = subprocess.run(
                [str(VENV_PYTHON), "-c",
                 "import torch; print(torch.backends.mps.is_available())"],
                capture_output=True, text=True,
            )
            info["mps_ok"] = r.stdout.strip() == "True"
            if info["mps_ok"]:
                info["backend"] = "mps"
        return info

    # NVIDIA detection
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            info["name"] = r.stdout.strip().split("\n")[0].strip()
            info["has_nvidia"] = bool(info["name"])
        if info["has_nvidia"]:
            r2 = subprocess.run(
                ["nvidia-smi"], capture_output=True, text=True, timeout=5,
            )
            m = re.search(r"CUDA Version:\s*(\d+)", r2.stdout)
            if m and int(m.group(1)) < 12:
                info["cuda_index_url"] = "cu118"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # AMD detection (skipped if NVIDIA already found — single-GPU assumption)
    if not info["has_nvidia"]:
        amd_name = _detect_amd_gpu()
        if amd_name:
            info["has_amd"] = True
            info["name"] = amd_name
            if is_windows:
                info["rocm_windows"] = True
                info["rocm_python_ok"] = sys.version_info[:2] == (3, 12)

    # Probe what the venv's torch actually has: cuda wheel vs rocm wheel
    # ROCm wheels still expose torch.cuda.is_available() — distinguish via torch.version.hip
    if VENV_PYTHON.is_file() and (info["has_nvidia"] or info["has_amd"]):
        r = subprocess.run(
            [str(VENV_PYTHON), "-c",
             "import torch; print(torch.cuda.is_available(), bool(getattr(torch.version, 'hip', None)))"],
            capture_output=True, text=True,
        )
        parts = r.stdout.strip().split()
        if len(parts) == 2:
            gpu_ok = parts[0] == "True"
            is_rocm = parts[1] == "True"
            if gpu_ok and is_rocm:
                info["rocm_ok"] = True
                info["backend"] = "rocm"
            elif gpu_ok:
                info["cuda_ok"] = True
                info["backend"] = "cuda"

    return info


def check_config():
    """Return (ok, has_gemini, has_dashscope)."""
    import json
    config_path = PROJECT_DIR / "local" / "config.json"
    has_gemini = False
    has_dashscope = False
    if config_path.is_file():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            has_gemini = bool(cfg.get("gemini_api_key"))
            has_dashscope = bool(cfg.get("dashscope_api_key"))
        except (json.JSONDecodeError, OSError):
            pass
    # Also check env vars
    has_gemini = has_gemini or bool(os.environ.get("GEMINI_API_KEY"))
    has_dashscope = has_dashscope or bool(os.environ.get("DASHSCOPE_API_KEY"))
    return True, has_gemini, has_dashscope


# ── Setup steps (unchanged logic; log callback → direct print) ──────────────────

def create_venv():
    """Create virtual environment."""
    print("  创建虚拟环境...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    print("  ✓ 虚拟环境创建完成")


def install_deps():
    """Run pip install with stdout streaming to terminal."""
    print("  安装依赖包...")
    cmd = [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"  {line}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"pip install failed (exit code {proc.returncode})")
    print("  ✓ 依赖包安装完成")


def download_model():
    """Download model via modelscope SDK."""
    print("  下载 BiRefNet 模型 (~840 MB)...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    script = (
        "import sys;"
        "from modelscope import snapshot_download;"
        "snapshot_download('AI-ModelScope/RMBG-2.0', local_dir=sys.argv[1], max_workers=4)"
    )
    cmd = [str(VENV_PYTHON), "-c", script, str(MODEL_DIR)]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.strip()
        if line:
            print(f"  {line}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Model download failed (exit code {proc.returncode})")
    print("  ✓ 模型下载完成")


def install_gpu_torch():
    """Install GPU-enabled PyTorch wheel based on detected backend."""
    gpu = check_gpu()
    if gpu["has_nvidia"]:
        suffix = gpu["cuda_index_url"]
        label = f"CUDA ({suffix})"
    elif gpu["has_amd"]:
        if gpu.get("rocm_windows"):
            return _install_rocm_windows()
        suffix = gpu["rocm_index_url"]
        label = f"ROCm ({suffix})"
    else:
        raise RuntimeError("未检测到 NVIDIA 或 AMD GPU，无需安装 GPU 版 PyTorch")

    print(f"  安装 GPU 版 PyTorch [{label}]，约 2-3 GB...")
    index_url = f"https://download.pytorch.org/whl/{suffix}"
    cmd = [
        str(VENV_PYTHON), "-m", "pip", "install",
        "torch", "torchvision", "--force-reinstall", "--index-url", index_url,
    ]
    _run_pip(cmd)
    print("  ✓ GPU 版 PyTorch 安装完成，重启应用后生效")


def _install_rocm_windows():
    """Install ROCm SDK + PyTorch wheels on Windows (Python 3.12 required)."""
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            f"Windows ROCm 需要 Python 3.12，当前为 Python {sys.version_info[0]}.{sys.version_info[1]}"
        )

    print("  安装 ROCm SDK（约 2-3 GB）...")
    cmd = [str(VENV_PYTHON), "-m", "pip", "install", "--no-cache-dir", *ROCM_WIN_SDK_WHEELS]
    _run_pip(cmd)
    print("  ✓ ROCm SDK 安装完成")

    print(f"  安装 PyTorch {ROCM_WIN_TORCH_VER}+rocm{ROCM_WIN_VERSION}（约 2-3 GB）...")
    cmd = [str(VENV_PYTHON), "-m", "pip", "install", "--no-cache-dir", *ROCM_WIN_TORCH_WHEELS]
    _run_pip(cmd)
    print("  ✓ Windows ROCm PyTorch 安装完成，重启应用后生效")


def _run_pip(cmd):
    """Run a pip command with streaming output."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"  {line}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"pip 安装失败 (exit {proc.returncode})")


# ── CLI interaction helpers ─────────────────────────────────────────────────────

def _print_banner():
    print("╔══════════════════════════════════════════╗")
    print("║   Image Processing Toolbox              ║")
    print("╚══════════════════════════════════════════╝")
    print()


def _gpu_status_line(gpu):
    """Return a one-line GPU status string."""
    if gpu['backend'] == 'rocm':
        return f"✅  {gpu['name']} · ROCm 已启用"
    elif gpu['backend'] == 'cuda':
        return f"✅  {gpu['name']} · CUDA 已启用"
    elif gpu['backend'] == 'mps':
        return f"✅  {gpu['name']} · MPS 已启用"
    elif gpu['has_nvidia']:
        return f"⚠️  {gpu['name']} · CUDA 未启用"
    elif gpu['has_amd']:
        reason = "Python 版本不符" if not gpu.get('rocm_python_ok', True) else "ROCm 未启用"
        return f"⚠️  {gpu['name']} · {reason}"
    else:
        return "💻  CPU 推理"


def _confirm_required(step_name):
    """Prompt for a required step. Returns True if confirmed, exits if declined."""
    ans = input(f"是否{step_name}？[Y/n] ").strip().lower()
    if ans in ("n", "no"):
        print("\n  已取消")
        sys.exit(0)
    return True


def _confirm_optional(step_name):
    """Prompt for an optional step. Returns True if explicitly confirmed."""
    ans = input(f"是否{step_name}？[y/N] ").strip().lower()
    return ans in ("y", "yes")


def _run_setup_step(step_fn):
    """Run a setup step, print divider, call function, catch errors."""
    print()
    try:
        step_fn()
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        sys.exit(1)


def _launch_gradio():
    """Start Gradio app.py and wait for it to finish."""
    print()
    print("✅ 环境就绪，启动应用...")
    print(f"   按 Ctrl+C 停止")
    print()

    cmd = [str(VENV_PYTHON), "app.py", "--open-browser"]
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_DIR))

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n  正在停止...")
        proc.terminate()
        proc.wait()
        print("  已停止")


# ── Main entry point ───────────────────────────────────────────────────────────

def main():
    _print_banner()

    # Phase 0: check Python
    py_ok, py_ver = check_python()
    if not py_ok:
        print(f"需要 Python >= 3.10，当前: {py_ver}")
        sys.exit(1)

    # Phase 1: environment check — print each result immediately
    print("🔍 环境检查:\n")

    print(f"   🐍 Python ............... {'✅' if py_ok else '❌'}  {py_ver}")

    venv_ok = check_venv()[0]
    print(f"   📦 虚拟环境 ............. {'✅  .venv 已就绪' if venv_ok else '❌  未创建'}")

    deps_missing = check_deps()
    deps_ok = len(deps_missing) == 0
    if deps_ok:
        print(f"   📚 依赖包 ............... ✅  全部已安装")
    else:
        print(f"   📚 依赖包 ............... ❌  缺少 {len(deps_missing)} 个: {', '.join(deps_missing)}")

    gpu = check_gpu()
    print(f"   🎮 GPU .................. {_gpu_status_line(gpu)}")

    model_ok = check_model()[0]
    if model_ok:
        print(f"   🧠 模型 ................. ✅  已下载")
    else:
        print(f"   🧠 模型 ................. ❌  需要下载 (~840 MB)")

    print()

    all_ready = venv_ok and deps_ok and model_ok

    # Phase 2: if ready, launch directly (zero interaction)
    if all_ready:
        _launch_gradio()
        return

    # Phase 3: setup wizard
    print("─" * 45)
    print("必装项:")
    if not venv_ok:
        print("  1. 创建虚拟环境")
    if not deps_ok:
        print("  2. 安装依赖包 (pip install -r requirements.txt)")
    if not model_ok:
        print(f"  3. 下载 BiRefNet 模型 (~840 MB)")

    show_gpu = (
        gpu['has_nvidia'] and not gpu['cuda_ok']
        or gpu['has_amd'] and not gpu['rocm_ok']
        and gpu.get('rocm_python_ok', True)
    )
    if show_gpu:
        gpu_label = "CUDA" if gpu['has_nvidia'] else "ROCm"
        print(f"\n可选:")
        print(f"  4. 安装 {gpu_label} 版 PyTorch 启用 GPU 加速 (约 2-3 GB)")
    print("─" * 45)

    # Required steps
    if not venv_ok:
        _confirm_required("创建虚拟环境")
        _run_setup_step(create_venv)

    if not deps_ok:
        _confirm_required("安装依赖包")
        _run_setup_step(install_deps)

    if not model_ok:
        _confirm_required("下载 BiRefNet 模型 (~840 MB)")
        _run_setup_step(download_model)

    # Optional GPU
    if show_gpu:
        gpu_label = "CUDA" if gpu['has_nvidia'] else "ROCm"
        if _confirm_optional(f"安装 {gpu_label} 版 PyTorch 启用 GPU 加速 (约 2-3 GB)"):
            _run_setup_step(install_gpu_torch)
        else:
            print("\n  跳过 GPU 支持（后续可在 Gradio 设置 Tab 查看安装命令）")

    # Launch
    _launch_gradio()


if __name__ == "__main__":
    main()
