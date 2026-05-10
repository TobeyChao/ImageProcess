#!/usr/bin/env python3
"""Image Processing Toolbox — zero-dependency bootstrap launcher.

Usage:
    python main.py

This script uses only Python stdlib so the user can run it immediately after
git clone, without any pip install.
"""

import http.server
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

HOST = "127.0.0.1"
PORT = 7860
GRADIO_PORT = 7861

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


# ── Environment check ──────────────────────────────────────────────────────────

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


def full_status():
    """Return a dict describing the environment."""
    py_ok, py_ver = check_python()
    venv_ok, venv_path = check_venv()
    missing_deps = check_deps()
    model_ok, model_path = check_model()
    _, has_gemini, has_dashscope = check_config()
    gpu = check_gpu()
    deps_ok = len(missing_deps) == 0

    ready = py_ok and venv_ok and deps_ok and model_ok

    return {
        "ready": ready,
        "python": {"ok": py_ok, "version": py_ver},
        "venv": {"ok": venv_ok, "path": venv_path},
        "deps": {"ok": deps_ok, "missing": missing_deps},
        "model": {"ok": model_ok, "path": model_path},
        "gpu": {
            "backend": gpu["backend"],
            "has_nvidia": gpu["has_nvidia"],
            "cuda_ok": gpu["cuda_ok"],
            "has_amd": gpu["has_amd"],
            "rocm_ok": gpu["rocm_ok"],
            "is_apple_silicon": gpu["is_apple_silicon"],
            "mps_ok": gpu["mps_ok"],
            "name": gpu["name"],
            "rocm_windows": gpu["rocm_windows"],
            "rocm_python_ok": gpu["rocm_python_ok"],
        },
        "config": {"gemini": has_gemini, "dashscope": has_dashscope},
    }


# ── Setup steps ────────────────────────────────────────────────────────────────

def create_venv(log):
    """Create virtual environment."""
    log("status", "Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    log("ok", "Virtual environment created")


def install_deps(log):
    """Run pip install."""
    log("status", "Installing dependencies...")
    cmd = [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log("pip", line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"pip install failed (exit code {proc.returncode})")
    log("ok", "Dependencies installed")


def download_model(log):
    """Download model via modelscope SDK."""
    log("status", "Downloading BiRefNet model (~840 MB)...")
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
            log("modelscope", line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Model download failed (exit code {proc.returncode})")
    log("ok", "Model downloaded")


def install_gpu_torch(log):
    """Install GPU-enabled PyTorch wheel based on detected backend (cuda or rocm)."""
    gpu = check_gpu()
    if gpu["has_nvidia"]:
        suffix = gpu["cuda_index_url"]
        label = f"CUDA ({suffix})"
    elif gpu["has_amd"]:
        if gpu.get("rocm_windows"):
            return _install_rocm_windows(log)
        suffix = gpu["rocm_index_url"]
        label = f"ROCm ({suffix})"
    else:
        raise RuntimeError("未检测到 NVIDIA 或 AMD GPU，无需安装 GPU 版 PyTorch")

    log("status", f"安装 GPU 版 PyTorch [{label}]，约 2-3 GB...")
    index_url = f"https://download.pytorch.org/whl/{suffix}"
    cmd = [
        str(VENV_PYTHON), "-m", "pip", "install",
        "torch", "torchvision", "--force-reinstall", "--index-url", index_url,
    ]
    _run_pip(cmd, log)
    log("ok", "GPU 版 PyTorch 安装完成，重启应用后生效")


def _install_rocm_windows(log):
    """Install ROCm SDK + PyTorch wheels on Windows (Python 3.12 required)."""
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            f"Windows ROCm 需要 Python 3.12，当前为 Python {sys.version_info[0]}.{sys.version_info[1]}"
        )

    # Step 1: Install ROCm SDK wheels
    log("status", "安装 ROCm SDK（约 2-3 GB）...")
    cmd = [
        str(VENV_PYTHON), "-m", "pip", "install",
        "--no-cache-dir", *ROCM_WIN_SDK_WHEELS,
    ]
    _run_pip(cmd, log)
    log("ok", "ROCm SDK 安装完成")

    # Step 2: Install PyTorch ROCm wheels
    log("status", f"安装 PyTorch {ROCM_WIN_TORCH_VER}+rocm{ROCM_WIN_VERSION}（约 2-3 GB）...")
    cmd = [
        str(VENV_PYTHON), "-m", "pip", "install",
        "--no-cache-dir", *ROCM_WIN_TORCH_WHEELS,
    ]
    _run_pip(cmd, log)
    log("ok", "Windows ROCm PyTorch 安装完成，重启应用后生效")


def _run_pip(cmd, log):
    """Run a pip command with streaming log output."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log("pip", line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"pip 安装失败 (exit {proc.returncode})")


# ── SSE event stream ───────────────────────────────────────────────────────────

class EventQueue:
    """Thread-safe queue for SSE events."""

    def __init__(self):
        self._queue = queue.Queue()
        self._done = threading.Event()

    def put(self, event_type, data):
        self._queue.put(json.dumps({"type": event_type, "data": data}))

    def get(self, timeout=0.5):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def finish(self):
        self._done.set()

    def is_finished(self):
        return self._done.is_set()


class SSEHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP server that serves setup page and SSE events."""

    event_queues = {}  # client_id -> EventQueue
    setup_events = None  # shared EventQueue during setup

    def log_message(self, format, *args):
        pass  # Suppress access logs

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_setup_page()
        elif parsed.path == "/api/status":
            self._send_json(full_status())
        elif parsed.path == "/api/gradio-ready":
            self._check_gradio_ready()
        elif parsed.path == "/api/events":
            self._handle_sse()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/setup/create-venv":
            self._run_setup_step(create_venv)
        elif parsed.path == "/api/setup/install-deps":
            self._run_setup_step(install_deps)
        elif parsed.path == "/api/setup/install-gpu-torch":
            self._run_setup_step(install_gpu_torch)
        elif parsed.path == "/api/setup/download-model":
            self._run_setup_step(download_model)
        elif parsed.path == "/api/launch":
            self._handle_launch()
        else:
            self.send_error(404)

    def _serve_setup_page(self):
        html = SETUP_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _check_gradio_ready(self):
        import socket
        ready = False
        try:
            s = socket.create_connection((HOST, GRADIO_PORT), timeout=1)
            s.close()
            ready = True
        except OSError:
            pass
        self._send_json({"ready": ready})

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        eq = EventQueue()
        SSEHandler.setup_events = eq

        try:
            while not eq.is_finished():
                msg = eq.get(timeout=1.0)
                if msg:
                    self.wfile.write(f"data: {msg}\n\n".encode())
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _run_setup_step(self, step_fn):
        eq = SSEHandler.setup_events
        if eq is None:
            self._send_json({"error": "No SSE connection"}, 400)
            return

        def log(event_type, data):
            eq.put(event_type, data)

        try:
            step_fn(log)
            eq.put("done", "ok")
            self._send_json({"ok": True})
        except Exception as e:
            eq.put("error", str(e))
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_launch(self):
        """Check status and launch Gradio if ready."""
        status = full_status()
        if not status["ready"]:
            self._send_json({"ok": False, "error": "环境未就绪"}, 400)
            return
        self._send_json({"ok": True, "message": "Launching..."})

        # Signal SSE to finish
        if SSEHandler.setup_events:
            SSEHandler.setup_events.finish()
            SSEHandler.setup_events = None

        threading.Thread(target=_delayed_shutdown, args=(self.server,), daemon=True).start()


def _delayed_shutdown(httpd):
    time.sleep(0.5)
    httpd.shutdown()
    httpd.server_close()


# ── Reverse proxy ──────────────────────────────────────────────────────────────

class ReverseProxyHandler(http.server.BaseHTTPRequestHandler):
    """Forward all requests to the Gradio backend."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/api/gradio-ready":
            self._check_gradio_ready()
        else:
            self._proxy()

    def _check_gradio_ready(self):
        import socket
        ready = False
        try:
            s = socket.create_connection((HOST, GRADIO_PORT), timeout=1)
            s.close()
            ready = True
        except OSError:
            pass
        body = json.dumps({"ready": ready}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self):
        import urllib.request
        url = f"http://{HOST}:{GRADIO_PORT}{self.path}"
        body = None
        if self.command in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                body = self.rfile.read(length)

        req = urllib.request.Request(
            url, data=body, method=self.command,
            headers={k: v for k, v in self.headers.items()
                     if k.lower() not in ("host", "connection")}
        )
        req.add_header("Connection", "close")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                skip = {"transfer-encoding", "content-length", "connection"}
                for key, val in resp.headers.items():
                    if key.lower() not in skip:
                        self.send_header(key, val)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read() or b""
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self._serve_starting_page()

    def _serve_starting_page(self):
        """Friendly 'starting up' HTML with auto-refresh, instead of bare 502."""
        body = (
            b'<!DOCTYPE html><html lang="zh-CN"><head>'
            b'<meta charset="UTF-8"><title>\xe5\x90\xaf\xe5\x8a\xa8\xe4\xb8\xad...</title>'
            b'<meta http-equiv="refresh" content="2">'
            b'<style>body{font-family:-apple-system,sans-serif;background:#1a1a2e;'
            b'color:#e0e0e0;min-height:100vh;display:flex;align-items:center;'
            b'justify-content:center;flex-direction:column;gap:16px}'
            b'.spinner{width:36px;height:36px;border:3px solid #333;'
            b'border-top:3px solid #6366f1;border-radius:50%;'
            b'animation:spin 0.8s linear infinite}'
            b'@keyframes spin{to{transform:rotate(360deg)}}'
            b'p{color:#888;font-size:13px}</style>'
            b'</head><body>'
            b'<div class="spinner"></div>'
            b'<p>Gradio \xe5\x90\xaf\xe5\x8a\xa8\xe4\xb8\xad\xef\xbc\x8c'
            b'\xe9\xa1\xb5\xe9\x9d\xa2\xe5\xb0\x86\xe5\x9c\xa8 2 \xe7\xa7\x92'
            b'\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe5\x88\xb7\xe6\x96\xb0...</p>'
            b'</body></html>'
        )
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Retry-After", "2")
        self.end_headers()
        self.wfile.write(body)

    do_POST = _proxy
    do_PUT = _proxy
    do_DELETE = _proxy


# ── Setup HTML page (inline) ───────────────────────────────────────────────────

SETUP_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Image Processing Toolbox - Setup</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #1a1a2e; color: #e0e0e0; min-height: 100vh; display: flex;
         align-items: center; justify-content: center; }
  .card { background: #16213e; border-radius: 16px; padding: 40px; max-width: 560px;
          width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.4); }
  h1 { font-size: 24px; margin-bottom: 8px; color: #e94560; }
  .subtitle { color: #888; font-size: 14px; margin-bottom: 24px; }
  .check-item { display: flex; align-items: center; gap: 10px; padding: 10px 0;
                border-bottom: 1px solid #1f3460; }
  .check-item .icon { font-size: 18px; width: 24px; text-align: center; }
  .check-item .name { font-weight: 600; min-width: 100px; }
  .check-item .status { color: #888; font-size: 14px; flex: 1; }
  .check-item .status.ok { color: #4ecca3; }
  .check-item .status.bad { color: #e94560; }
  .buttons { margin-top: 24px; display: flex; gap: 12px; flex-wrap: wrap; }
  button { padding: 12px 24px; border: none; border-radius: 8px; font-size: 15px;
           font-weight: 600; cursor: pointer; transition: all 0.2s; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-primary { background: #e94560; color: #fff; }
  .btn-primary:hover:not(:disabled) { background: #d63851; }
  .btn-secondary { background: #1f3460; color: #e0e0e0; }
  .btn-secondary:hover:not(:disabled) { background: #25417a; }
  .btn-launch { background: #4ecca3; color: #1a1a2e; }
  .btn-launch:hover:not(:disabled) { background: #3db88f; }
  #log { background: #0f0f23; border-radius: 8px; padding: 16px; margin-top: 16px;
         font-family: "SF Mono", "Monaco", "Menlo", monospace; font-size: 12px;
         max-height: 200px; overflow-y: auto; display: none; line-height: 1.6; }
  .pip-line { color: #aaa; }
  .progress-line { color: #f0c040; }
  .error-line { color: #e94560; }
  .ok-line { color: #4ecca3; font-weight: 600; }
  .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid #333;
             border-top: 2px solid #e94560; border-radius: 50%; animation: spin 0.6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .all-ready { text-align: center; padding: 20px 0; }
  .all-ready .big-icon { font-size: 48px; margin-bottom: 12px; }
  .all-ready p { color: #4ecca3; font-size: 18px; }
</style>
</head>
<body>
<div class="card">
  <h1>Image Processing Toolbox</h1>
  <p class="subtitle">环境初始化向导</p>

  <div id="checks">
    <div class="check-item"><span class="icon" id="icon-py">⏳</span><span class="name">Python</span><span class="status" id="st-py">检测中...</span></div>
    <div class="check-item"><span class="icon" id="icon-venv">⏳</span><span class="name">虚拟环境</span><span class="status" id="st-venv">检测中...</span></div>
    <div class="check-item"><span class="icon" id="icon-deps">⏳</span><span class="name">依赖</span><span class="status" id="st-deps">检测中...</span></div>
    <div class="check-item"><span class="icon" id="icon-model">⏳</span><span class="name">模型</span><span class="status" id="st-model">检测中...</span></div>
    <div class="check-item"><span class="icon" id="icon-gpu">⏳</span><span class="name">GPU 加速</span><span class="status" id="st-gpu">检测中...</span></div>
  </div>

  <div id="all-ready" style="display:none">
    <div class="all-ready">
      <div class="big-icon">✅</div>
      <p>环境就绪！</p>
    </div>
  </div>

  <div class="buttons">
    <button id="btn-venv" class="btn-primary" disabled>创建虚拟环境</button>
    <button id="btn-deps" class="btn-primary" disabled>安装依赖</button>
    <button id="btn-gpu" class="btn-secondary" disabled style="display:none">安装 GPU 支持</button>
    <button id="btn-model" class="btn-primary" disabled>下载模型</button>
    <button id="btn-launch" class="btn-launch" disabled>启动应用</button>
  </div>

  <div id="log"></div>
</div>

<script>
let status = {};
const logEl = document.getElementById('log');

function showLog() { logEl.style.display = 'block'; }
function logLine(cls, text) {
  showLog();
  const div = document.createElement('div');
  div.className = cls;
  div.textContent = text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

async function refreshStatus() {
  const resp = await fetch('/api/status');
  status = await resp.json();
  updateUI();
}

function updateUI() {
  setCheck('py', 'Python', status.python.ok, status.python.version, status.python.ok ? 'OK' : '需要 ≥ 3.10');
  setCheck('venv', '虚拟环境', status.venv.ok, status.venv.ok ? '.venv 已就绪' : '未创建', status.venv.ok ? 'OK' : '未创建');
  setCheck('deps', '依赖', status.deps.ok, status.deps.ok ? '全部已安装' : `缺少: ${status.deps.missing.join(', ')}`,
           status.deps.ok ? 'OK' : `${status.deps.missing.length} 个缺失`);
  setCheck('model', '模型', status.model.ok, status.model.ok ? '已下载' : '未下载 (840MB)',
           status.model.ok ? 'OK' : '未下载');

  // GPU check
  const gpu = status.gpu;
  const gpuBtn = document.getElementById('btn-gpu');
  if (gpu.is_apple_silicon) {
    if (gpu.mps_ok) {
      setCheck('gpu', 'GPU 加速', true, gpu.name + ' · MPS 已启用', 'MPS');
    } else {
      setCheck('gpu', 'GPU 加速', true, gpu.name + ' · 等待依赖安装后启用 MPS', 'MPS 待启用');
    }
    gpuBtn.style.display = 'none';
  } else if (gpu.has_nvidia) {
    if (gpu.cuda_ok) {
      setCheck('gpu', 'GPU 加速', true, gpu.name + ' · CUDA 已启用', 'CUDA');
      gpuBtn.style.display = 'none';
    } else {
      setCheck('gpu', 'GPU 加速', false, gpu.name + ' · 未启用 CUDA，建议安装 GPU 支持', '未启用');
      gpuBtn.textContent = '安装 CUDA 版 PyTorch';
      gpuBtn.style.display = '';
      gpuBtn.disabled = !status.deps.ok;
    }
  } else if (gpu.has_amd) {
    if (gpu.rocm_ok) {
      setCheck('gpu', 'GPU 加速', true, gpu.name + ' · ROCm 已启用', 'ROCm');
      gpuBtn.style.display = 'none';
    } else if (gpu.rocm_windows && !gpu.rocm_python_ok) {
      setCheck('gpu', 'GPU 加速', false, gpu.name + ' · ROCm 需要 Python 3.12，当前 ' + status.python.version, 'Python 版本不符');
      gpuBtn.textContent = '安装 ROCm 版 PyTorch（需要 Python 3.12）';
      gpuBtn.style.display = '';
      gpuBtn.disabled = true;
    } else {
      setCheck('gpu', 'GPU 加速', false, gpu.name + ' · 未启用 ROCm，建议安装 GPU 支持（实验性）', '未启用');
      gpuBtn.textContent = gpu.rocm_windows ? '安装 ROCm 版 PyTorch' : '安装 ROCm 版 PyTorch（实验性）';
      gpuBtn.style.display = '';
      gpuBtn.disabled = !status.deps.ok;
    }
  } else {
    setCheck('gpu', 'GPU 加速', true, '未检测到独立 GPU，使用 CPU 推理', 'CPU');
    gpuBtn.style.display = 'none';
  }

  document.getElementById('btn-venv').disabled = status.venv.ok;
  document.getElementById('btn-deps').disabled = !status.venv.ok || status.deps.ok;
  document.getElementById('btn-model').disabled = !status.deps.ok || status.model.ok;
  document.getElementById('btn-launch').disabled = !status.ready;

  if (status.ready) {
    document.getElementById('all-ready').style.display = 'block';
  }
}

function setCheck(id, name, ok, detail, short) {
  document.getElementById(`icon-${id}`).textContent = ok ? '✅' : '❌';
  const el = document.getElementById(`st-${id}`);
  el.textContent = detail;
  el.title = short;
  el.className = ok ? 'status ok' : 'status bad';
}

async function step(url, label) {
  logEl.innerHTML = '';
  showLog();
  logLine('ok-line', `▶ ${label}...`);

  const evtSource = new EventSource('/api/events');
  return new Promise((resolve, reject) => {
    evtSource.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'pip') logLine('pip-line', msg.data);
      else if (msg.type === 'progress') logLine('progress-line', msg.data);
      else if (msg.type === 'error') logLine('error-line', '❌ ' + msg.data);
      else if (msg.type === 'ok') logLine('ok-line', '✓ ' + msg.data);
      else if (msg.type === 'done') { evtSource.close(); resolve(); }
    };
    evtSource.onerror = () => { evtSource.close(); reject(new Error('SSE error')); };

    // Start the step AFTER opening SSE (need a small delay)
    setTimeout(async () => {
      try {
        const resp = await fetch(url, { method: 'POST' });
        const data = await resp.json();
        if (!data.ok) {
          logLine('error-line', '❌ ' + (data.error || 'Unknown error'));
          evtSource.close();
          reject(new Error(data.error));
        }
      } catch (err) {
        logLine('error-line', '❌ ' + err.message);
        evtSource.close();
        reject(err);
      }
    }, 500);
  });
}

async function runStep(btnId, url, label) {
  const btn = document.getElementById(btnId);
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> ' + label;
  try {
    await step(url, label);
    await refreshStatus();
  } catch (err) {
    console.error(err);
  }
  btn.innerHTML = label;
  btn.disabled = false;
}

document.getElementById('btn-venv').onclick = () => runStep('btn-venv', '/api/setup/create-venv', '创建虚拟环境');
document.getElementById('btn-deps').onclick = () => runStep('btn-deps', '/api/setup/install-deps', '安装依赖');
document.getElementById('btn-gpu').onclick = () => runStep('btn-gpu', '/api/setup/install-gpu-torch', '安装 GPU 支持');
document.getElementById('btn-model').onclick = () => runStep('btn-model', '/api/setup/download-model', '下载模型');
document.getElementById('btn-launch').onclick = async () => {
  const btn = document.getElementById('btn-launch');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 启动中...';
  await fetch('/api/launch', { method: 'POST' });
  function waitForGradio() {
    fetch('/api/gradio-ready')
      .then(r => r.json())
      .then(data => {
        if (data.ready) window.location.href = '/';
        else setTimeout(waitForGradio, 2000);
      })
      .catch(() => setTimeout(waitForGradio, 2000));
  }
  setTimeout(waitForGradio, 1000);
};

// Initial check
refreshStatus();
</script>
</body>

</body>
</html>"""


# ── Main entry point ───────────────────────────────────────────────────────────

def run_setup_server():
    """Run the setup HTTP server. Blocks until shutdown()."""
    server = http.server.ThreadingHTTPServer((HOST, PORT), SSEHandler)
    print(f"\n  浏览器打开: http://{HOST}:{PORT}")
    print(f"  按 Ctrl+C 停止\n")
    webbrowser.open(f"http://{HOST}:{PORT}")
    return server


def run_gradio_server():
    """Start Gradio app.py as a subprocess."""
    cmd = [str(VENV_PYTHON), "app.py"]
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_DIR))
    return proc


def run_proxy():
    """Start reverse proxy from PORT to GRADIO_PORT."""
    server = http.server.ThreadingHTTPServer((HOST, PORT), ReverseProxyHandler)

    def _serve():
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    threading.Thread(target=_serve, daemon=True).start()
    return server


def wait_for_gradio(timeout: float = 60.0, interval: float = 0.3) -> bool:
    """Poll GRADIO_PORT until something accepts a connection. Returns True if ready."""
    import socket
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            s = socket.create_connection((HOST, GRADIO_PORT), timeout=0.5)
            s.close()
            return True
        except OSError:
            time.sleep(interval)
    return False


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Image Processing Toolbox              ║")
    print("╚══════════════════════════════════════════╝\n")

    # Phase 0: check Python
    py_ok, py_ver = check_python()
    if not py_ok:
        print(f"需要 Python >= 3.10，当前: {py_ver}")
        sys.exit(1)

    # Phase 1: check environment (one by one for live progress)
    print("🔍 环境检查:")

    print("   🐍 Python...", end=" ", flush=True)
    py_ok, py_ver = check_python()
    print(f"{'✅' if py_ok else '❌'}  {py_ver}")

    print("   📦 虚拟环境...", end=" ", flush=True)
    venv_ok, venv_path = check_venv()
    print(f"{'✅' if venv_ok else '❌ 需要创建'}  {venv_path}")

    print("   📚 依赖包...", end=" ", flush=True)
    missing_deps = check_deps()
    deps_ok = len(missing_deps) == 0
    if deps_ok:
        print("✅ 全部已安装")
    else:
        print(f"❌ 缺少 {len(missing_deps)} 个: {', '.join(missing_deps)}")

    print("   🎮 GPU...", end=" ", flush=True)
    gpu = check_gpu()
    if gpu['backend'] == 'rocm':
        print(f"✅ {gpu['name']} · ROCm")
    elif gpu['backend'] == 'cuda':
        print(f"✅ {gpu['name']} · CUDA")
    elif gpu['backend'] == 'mps':
        print(f"✅ {gpu['name']} · MPS")
    elif gpu['has_amd']:
        print(f"⚠️ {gpu['name']} · 未启用")
    elif gpu['has_nvidia']:
        print(f"⚠️ {gpu['name']} · 未启用")
    else:
        print("💻 CPU 推理")

    print("   🧠 模型...", end=" ", flush=True)
    model_ok, model_path = check_model()
    print(f"{'✅' if model_ok else '❌ 需要下载'}  {model_path}")

    # Build status dict for downstream use
    _, has_gemini, has_dashscope = check_config()
    ready = py_ok and venv_ok and deps_ok and model_ok

    class Status:
        def __init__(s):
            s.ready = ready
            s.python = {"ok": py_ok, "version": py_ver}
            s.venv = {"ok": venv_ok, "path": venv_path}
            s.deps = {"ok": deps_ok, "missing": missing_deps}
            s.model = {"ok": model_ok, "path": model_path}
            s.gpu = gpu
            s.config = {"gemini": has_gemini, "dashscope": has_dashscope}

    status = Status()

    if status.ready:
        print(f"\n✅ 环境就绪，启动应用...\n")
        # Start Gradio directly and proxy
        gradio_proc = run_gradio_server()
        print(f"⏳ 等待 Gradio 监听 {HOST}:{GRADIO_PORT} ...", end="", flush=True)
        if wait_for_gradio(timeout=60.0):
            print(" ✅")
        else:
            print(" ⚠️ 超时（60s），仍尝试打开浏览器")
        print(f"🌐 浏览器打开: http://{HOST}:{PORT}\n")
        webbrowser.open(f"http://{HOST}:{PORT}")
        proxy = http.server.ThreadingHTTPServer((HOST, PORT), ReverseProxyHandler)
        try:
            proxy.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            gradio_proc.terminate()
            gradio_proc.wait()
        return

    print(f"模型: {'✓' if status.model['ok'] else '✗ 需要下载 (~840 MB)'}")

    # Phase 2: setup wizard
    print(f"\n🛠️ 启动环境初始化向导...")
    server = run_setup_server()
    server.serve_forever()

    # Phase 3: setup complete, launch Gradio
    print("\n✅ 环境初始化完成，启动应用...\n")
    gradio_proc = run_gradio_server()
    proxy = run_proxy()
    print(f"🚀 Gradio 启动中: http://{HOST}:{PORT}\n")

    try:
        gradio_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        gradio_proc.terminate()
        gradio_proc.wait()
        proxy.shutdown()


if __name__ == "__main__":
    main()
