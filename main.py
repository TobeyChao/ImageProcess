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
    ("pillow", "PIL"),
    ("numpy", "numpy"),
    ("google-genai", "google"),
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
    missing = []
    for display_name, import_name in REQUIRED_DEPS:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", f"import {import_name}"],
            capture_output=True,
        )
        if result.returncode != 0:
            missing.append(display_name)
    return missing


def check_model():
    """Return (ok, path)."""
    ok = MODEL_KEY_FILE.is_file()
    return ok, str(MODEL_DIR)


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
    deps_ok = len(missing_deps) == 0

    ready = py_ok and venv_ok and deps_ok and model_ok

    return {
        "ready": ready,
        "python": {"ok": py_ok, "version": py_ver},
        "venv": {"ok": venv_ok, "path": venv_path},
        "deps": {"ok": deps_ok, "missing": missing_deps},
        "model": {"ok": model_ok, "path": model_path},
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
    """Download model via modelscope CLI."""
    log("status", "Downloading BiRefNet model (~840 MB)...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(VENV_PYTHON), "-m", "modelscope",
        "download", "--model", "AI-ModelScope/RMBG-2.0",
        "--local_dir", str(MODEL_DIR),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log("modelscope", line)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("PROGRESS:"):
            log("progress", line[9:])
        elif line.startswith("ERROR:"):
            log("error", line[6:])
        elif line:
            log("modelscope", line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Model download failed (exit code {proc.returncode})")
    log("ok", "Model downloaded")


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

        # The main thread will detect the server stopping and launch Gradio
        threading.Thread(target=_delayed_shutdown, args=(self.server,), daemon=True).start()


def _delayed_shutdown(httpd):
    time.sleep(0.5)
    httpd.shutdown()


# ── Reverse proxy ──────────────────────────────────────────────────────────────

class ReverseProxyHandler(http.server.BaseHTTPRequestHandler):
    """Forward all requests to the Gradio backend."""

    def log_message(self, format, *args):
        pass

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

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                self.send_header("Content-Type", content_type)
                # Forward other headers
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding",):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read() or b"")
        except Exception as e:
            self.send_error(502, str(e))

    do_GET = _proxy
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
document.getElementById('btn-model').onclick = () => runStep('btn-model', '/api/setup/download-model', '下载模型');
document.getElementById('btn-launch').onclick = async () => {
  const btn = document.getElementById('btn-launch');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 启动中...';
  await fetch('/api/launch', { method: 'POST' });
  // The page will redirect when Gradio starts
  setTimeout(() => { window.location.href = '/'; }, 3000);
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
    server = http.server.HTTPServer((HOST, PORT), SSEHandler)
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
    server = http.server.HTTPServer((HOST, PORT), ReverseProxyHandler)

    def _serve():
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    threading.Thread(target=_serve, daemon=True).start()
    return server


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Image Processing Toolbox              ║")
    print("╚══════════════════════════════════════════╝\n")

    # Phase 0: check Python
    py_ok, py_ver = check_python()
    if not py_ok:
        print(f"需要 Python >= 3.10，当前: {py_ver}")
        sys.exit(1)

    # Phase 1: check environment
    status = full_status()
    print(f"Python {py_ver}  ✓")
    print(f"虚拟环境: {'✓' if status['venv']['ok'] else '✗ 需要创建'}")
    missing_count = len(status['deps']['missing'])
    print(f"依赖: {'✓ 全部已安装' if status['deps']['ok'] else f'✗ 缺少 {missing_count} 个包'}")

    if status["ready"]:
        print(f"模型: ✓")
        print(f"\n  环境就绪，启动应用...\n")
        # Start Gradio directly and proxy
        gradio_proc = run_gradio_server()
        print(f"  Gradio 启动中...")
        time.sleep(3)
        print(f"  浏览器打开: http://{HOST}:{PORT}\n")
        webbrowser.open(f"http://{HOST}:{PORT}")
        proxy = http.server.HTTPServer((HOST, PORT), ReverseProxyHandler)
        try:
            proxy.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            gradio_proc.terminate()
            gradio_proc.wait()
        return

    print(f"模型: {'✓' if status['model']['ok'] else '✗ 需要下载 (~840 MB)'}")

    # Phase 2: setup wizard
    print(f"\n  启动环境初始化向导...")
    server = run_setup_server()
    server.serve_forever()

    # Phase 3: setup complete, launch Gradio
    print("\n  环境初始化完成，启动应用...\n")
    gradio_proc = run_gradio_server()
    time.sleep(3)
    proxy = run_proxy()
    print(f"  Gradio 已启动: http://{HOST}:{PORT}\n")

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
