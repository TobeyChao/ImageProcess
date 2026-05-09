# App 全面重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `app.py`（491 行单文件 Gradio 应用）重构为模块化结构 + C 布局 UI（侧边栏 / 主区 / 历史画廊）+ 鲁棒性强化。分 3 个 PR 推进。

**Architecture:** 守 Gradio 5.x，新增 `core/` 处理纯逻辑（config / api_keys / errors / history / state / skills），新增 `ui/` 处理界面（layout / theme / toast / tooltips / views/*）。原 `.claude/skills/*/scripts/` 保持不动，由 `core/skills.py` 加载并被 view 调用。

**Tech Stack:** Python ≥ 3.10、Gradio 5.x、PIL、numpy、torch、google-genai、requests、pytest（新增）

**Spec:** [docs/superpowers/specs/2026-05-09-app-refactor-design.md](../specs/2026-05-09-app-refactor-design.md)

---

## 命名约定

- 路径以仓库根 `e:\Proj\ImageProcess\` 为基准，正文用 POSIX 斜杠（git 友好）
- 每条 commit 信息末尾必须加 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`（参见仓库现有 commit 风格）
- 所有命令在仓库根目录执行（venv 已激活：`source .venv/bin/activate` 或 PowerShell 用 `.venv\Scripts\Activate.ps1`）
- 测试运行：`pytest tests/ -v`

---

# PR 1 · 后端重构（无 UI 改动）

## Task 1: 测试基础设施

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `requirements-dev.txt`
- Modify: `.gitignore`

- [ ] **Step 1: 新建 tests 包占位**

```bash
mkdir -p tests/fixtures
```

Write `tests/__init__.py`:
```python
```

- [ ] **Step 2: 写 conftest.py（共享 tmp 目录 fixture）**

Write `tests/conftest.py`:
```python
"""Shared pytest fixtures."""
import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A throwaway project root with local/ subtree."""
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "output").mkdir()
    return tmp_path


@pytest.fixture
def tmp_config(tmp_project: Path) -> Path:
    """Empty config.json path inside tmp_project."""
    return tmp_project / "local" / "config.json"


@pytest.fixture
def written_config(tmp_config: Path):
    """Helper that writes JSON and returns the path."""
    def _write(data: dict) -> Path:
        tmp_config.write_text(json.dumps(data), encoding="utf-8")
        return tmp_config
    return _write
```

- [ ] **Step 3: 写 dev 依赖文件**

Write `requirements-dev.txt`:
```
pytest>=8.0
pytest-mock>=3.12
```

- [ ] **Step 4: gitignore 加 .superpowers/、.pytest_cache、tests 临时**

Append to `.gitignore`:
```
# Pytest
.pytest_cache/
__pycache__/

# Brainstorming sessions
.superpowers/
```

- [ ] **Step 5: 安装 dev 依赖**

```bash
pip install -r requirements-dev.txt
```
Expected: 安装成功，无错误。

- [ ] **Step 6: 验证 pytest 能跑（空套件）**

```bash
pytest tests/ -v
```
Expected: `no tests ran in ...` 或 `1 warning`，无 ERROR。

- [ ] **Step 7: Commit**

```bash
git add tests/ requirements-dev.txt .gitignore
git commit -m "$(cat <<'EOF'
chore: 添加 pytest 测试基础设施

- 新增 tests/conftest.py 提供 tmp_project / tmp_config / written_config fixture
- 新增 requirements-dev.txt 声明 pytest 与 pytest-mock
- .gitignore 增补 .pytest_cache/、.superpowers/

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: core/config.py

**Files:**
- Create: `core/__init__.py`
- Create: `core/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 写 test_config.py 的失败测试**

Write `tests/test_config.py`:
```python
"""Tests for core.config — config.json read/write + schema migration."""
import json
import os
from pathlib import Path

import pytest

from core import config as cfg


def test_load_returns_empty_dict_when_no_file(tmp_config: Path):
    assert cfg.load(tmp_config) == {}


def test_load_returns_empty_dict_when_corrupt(tmp_config: Path):
    tmp_config.write_text("{not json", encoding="utf-8")
    assert cfg.load(tmp_config) == {}


def test_load_round_trip(tmp_config: Path):
    cfg.save(tmp_config, {"theme": "dark", "model_dir": "/x"})
    assert cfg.load(tmp_config) == {"theme": "dark", "model_dir": "/x"}


def test_get_value_priority_config_over_env(written_config, monkeypatch):
    path = written_config({"gemini_api_key": "from_config"})
    monkeypatch.setenv("GEMINI_API_KEY", "from_env")
    assert cfg.get_value(path, "gemini_api_key", env_var="GEMINI_API_KEY") == "from_config"


def test_get_value_falls_back_to_env(tmp_config: Path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from_env")
    assert cfg.get_value(tmp_config, "gemini_api_key", env_var="GEMINI_API_KEY") == "from_env"


def test_get_value_returns_default(tmp_config: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert cfg.get_value(tmp_config, "missing", default="x") == "x"


def test_save_atomic(tmp_config: Path, monkeypatch):
    """Writing to a non-empty file should not corrupt it on simulated failure."""
    cfg.save(tmp_config, {"a": 1})

    # Patch json.dump to raise mid-write
    import json as _json
    original = _json.dump
    def fail(*args, **kwargs):
        raise RuntimeError("simulated")
    monkeypatch.setattr("core.config.json.dump", fail)

    with pytest.raises(RuntimeError):
        cfg.save(tmp_config, {"a": 2})

    # Original file must remain intact
    assert _json.loads(tmp_config.read_text(encoding="utf-8")) == {"a": 1}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_config.py -v
```
Expected: ImportError 或 7 个 FAIL（`core` 还没创建）。

- [ ] **Step 3: 写 core/__init__.py 和 core/config.py**

Write `core/__init__.py`:
```python
"""Pure-logic core modules — no Gradio dependencies."""
```

Write `core/config.py`:
```python
"""Config file read/write with atomic save and env-var fallback.

Schema (local/config.json):
    model_dir, gemini_api_key, dashscope_api_key,
    theme ∈ {"light", "dark"}, last_view, history_filter,
    default_model ∈ {"gemini", "wan"}, default_ratio, default_size

Old configs missing new fields fall back to defaults at read time.
"""
import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "model_dir": "",
    "gemini_api_key": "",
    "dashscope_api_key": "",
    "theme": "light",
    "last_view": "rmbg",
    "history_filter": "all",
    "default_model": "gemini",
    "default_ratio": "1:1",
    "default_size": "1K",
}


def load(path: Path) -> dict[str, Any]:
    """Load config; returns {} if missing or corrupt."""
    if not Path(path).is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: serialize to .tmp then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def get_value(path: Path, key: str, env_var: str | None = None,
              default: Any = None) -> Any:
    """Priority: config file > env var > supplied default > DEFAULTS[key]."""
    data = load(path)
    val = data.get(key)
    if val:
        return val
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]
    if default is not None:
        return default
    return DEFAULTS.get(key, "")


def update(path: Path, **kwargs) -> dict[str, Any]:
    """Merge kwargs into existing config and save. Returns merged dict."""
    data = load(path)
    for k, v in kwargs.items():
        if v is not None and v != "":
            data[k] = v
    save(path, data)
    return data
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_config.py -v
```
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add core/ tests/test_config.py
git commit -m "$(cat <<'EOF'
refactor: 抽离 core/config 处理配置文件读写

- 原子写（写 .tmp 后 os.replace），异常时不会留下半成品
- get_value 优先级：config.json > 环境变量 > 默认
- DEFAULTS 提供新字段的兜底值，旧 config 无需迁移

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: core/api_keys.py

**Files:**
- Create: `core/api_keys.py`
- Create: `tests/test_api_keys.py`

- [ ] **Step 1: 写测试**

Write `tests/test_api_keys.py`:
```python
"""Tests for core.api_keys — unified key resolution + env injection."""
import os
from pathlib import Path

import pytest

from core import api_keys


def test_resolve_gemini_from_config(written_config):
    path = written_config({"gemini_api_key": "g-test"})
    assert api_keys.resolve(path, "gemini") == "g-test"


def test_resolve_dashscope_from_config(written_config):
    path = written_config({"dashscope_api_key": "d-test"})
    assert api_keys.resolve(path, "wan") == "d-test"


def test_resolve_falls_back_to_env(tmp_config: Path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-env")
    assert api_keys.resolve(tmp_config, "gemini") == "g-env"


def test_resolve_unknown_model_raises(tmp_config: Path):
    with pytest.raises(ValueError, match="unknown model"):
        api_keys.resolve(tmp_config, "unknown")


def test_resolve_returns_empty_when_missing(tmp_config: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    assert api_keys.resolve(tmp_config, "gemini") == ""


def test_use_api_key_sets_env(written_config, monkeypatch):
    path = written_config({"gemini_api_key": "g-test"})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with api_keys.use_api_key(path, "gemini"):
        assert os.environ["GEMINI_API_KEY"] == "g-test"

    # Restored
    assert "GEMINI_API_KEY" not in os.environ


def test_use_api_key_restores_existing(written_config, monkeypatch):
    path = written_config({"gemini_api_key": "g-new"})
    monkeypatch.setenv("GEMINI_API_KEY", "g-old")

    with api_keys.use_api_key(path, "gemini"):
        assert os.environ["GEMINI_API_KEY"] == "g-new"

    assert os.environ["GEMINI_API_KEY"] == "g-old"


def test_use_api_key_missing_raises(tmp_config: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(api_keys.MissingKey, match="Gemini"):
        with api_keys.use_api_key(tmp_config, "gemini"):
            pass
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_api_keys.py -v
```
Expected: 8 FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

Write `core/api_keys.py`:
```python
"""Unified API key resolution for Gemini and DashScope (Wan2.7).

Replaces the duplicated key-handling logic that previously appeared in
bwgen / gen-image / pipeline tabs. One place to add a new model backend.
"""
import os
from contextlib import contextmanager
from pathlib import Path

from core import config as cfg

# model_id -> (config_key, env_var, display_name)
KEY_SPECS = {
    "gemini": ("gemini_api_key", "GEMINI_API_KEY", "Gemini"),
    "wan": ("dashscope_api_key", "DASHSCOPE_API_KEY", "DashScope (Wan2.7)"),
}


class MissingKey(RuntimeError):
    """Raised when a required API key is not configured anywhere."""


def resolve(config_path: Path, model: str) -> str:
    """Return the API key for `model`, or "" if not configured."""
    if model not in KEY_SPECS:
        raise ValueError(f"unknown model: {model}")
    config_key, env_var, _ = KEY_SPECS[model]
    return cfg.get_value(config_path, config_key, env_var=env_var, default="")


@contextmanager
def use_api_key(config_path: Path, model: str):
    """Context manager that sets the env var for the model's SDK and
    restores the previous value on exit. Raises MissingKey if absent."""
    if model not in KEY_SPECS:
        raise ValueError(f"unknown model: {model}")
    _, env_var, display = KEY_SPECS[model]

    key = resolve(config_path, model)
    if not key:
        raise MissingKey(f"未配置 {display} API Key，请到设置页填写")

    previous = os.environ.get(env_var)
    os.environ[env_var] = key
    try:
        yield key
    finally:
        if previous is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = previous
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_api_keys.py -v
```
Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add core/api_keys.py tests/test_api_keys.py
git commit -m "$(cat <<'EOF'
refactor: 抽离 core/api_keys 统一处理 API Key

- resolve() 复用 core.config.get_value 的 config>env>default 优先级
- use_api_key() 上下文管理器临时注入环境变量并保证还原
- KEY_SPECS 表驱动，新增模型只需加一行
- MissingKey 异常携带友好显示名

替换原 app.py 中 3 处重复的 key 解析逻辑（bwgen/gen/pipeline）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: core/errors.py

**Files:**
- Create: `core/errors.py`
- Create: `tests/test_errors.py`

- [ ] **Step 1: 写测试**

Write `tests/test_errors.py`:
```python
"""Tests for core.errors — exception → user-friendly Chinese message."""
import pytest

from core import errors


def test_file_not_found_translated():
    msg, hint = errors.user_message(FileNotFoundError("no such file: /x/y.png"))
    assert "找不到文件" in msg
    assert "请检查路径" in hint


def test_permission_error_translated():
    msg, hint = errors.user_message(PermissionError("locked"))
    assert "没有权限" in msg


def test_api_key_error_matches_401():
    msg, hint = errors.user_message(RuntimeError("HTTP 401 Unauthorized"))
    assert "API Key 无效" in msg
    assert "设置" in hint


def test_api_key_error_matches_keyword():
    msg, hint = errors.user_message(RuntimeError("invalid api key xxx"))
    assert "API Key 无效" in msg


def test_rate_limit_429():
    msg, _ = errors.user_message(RuntimeError("HTTP 429 too many requests"))
    assert "频繁" in msg


def test_quota_exceeded():
    msg, _ = errors.user_message(RuntimeError("quota exceeded"))
    assert "配额" in msg


def test_oom_translated():
    msg, _ = errors.user_message(RuntimeError("CUDA out of memory at line 5"))
    assert "显存不足" in msg


def test_model_missing():
    msg, _ = errors.user_message(FileNotFoundError("model.safetensors not found"))
    assert ("模型" in msg) or ("找不到文件" in msg)


def test_size_mismatch():
    msg, _ = errors.user_message(ValueError("两张图片尺寸不一致 something"))
    assert "尺寸不一致" in msg


def test_unknown_error_falls_back():
    msg, hint = errors.user_message(RuntimeError("very weird thing happened"))
    assert "RuntimeError" in msg
    assert "very weird thing happened" in msg
    assert "日志" in hint
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_errors.py -v
```
Expected: 10 FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

Write `core/errors.py`:
```python
"""Translate raw exceptions into Chinese user-facing messages.

Each entry in ERROR_PATTERNS is (matcher, message_template, hint).
Matcher is either an exception class (isinstance check) or a callable
(exc) -> bool. First match wins. If nothing matches we return the raw
type+message and tell the user to check logs.
"""
from typing import Callable, Union

Matcher = Union[type, Callable[[Exception], bool]]
Pattern = tuple[Matcher, str, str]


def _has(*needles: str):
    """Build a matcher that returns True if any needle is in str(exc).lower()."""
    def _check(exc: Exception) -> bool:
        s = str(exc).lower()
        return any(n.lower() in s for n in needles)
    return _check


# Order matters — earlier patterns win.
ERROR_PATTERNS: list[Pattern] = [
    # Image dimension mismatch (must come before generic ValueError fallthrough)
    (_has("尺寸不一致", "size differ"),
     "黑底图和白底图尺寸不一致", "请确认两张图来自同一拍摄"),

    # API key family
    (_has("api key", "401", "unauthorized", "invalid_api_key"),
     "API Key 无效或已过期", "请到「设置」检查 Key 是否正确"),
    (_has("rate limit", "429", "throttling", "too many requests"),
     "API 调用太频繁，请稍后再试", "建议等待 30 秒后重试"),
    (_has("quota", "billing", "insufficient_quota"),
     "API 配额已用完", "请检查 API 控制台账单"),
    (_has("safety", "blocked"),
     "内容被安全过滤器拦截", "请修改提示词后重试"),

    # GPU / model
    (_has("cuda out of memory", "out of memory"),
     "显存不足", "尝试关闭其他占用 GPU 的程序，或在设置中改用 CPU"),
    (_has("model.safetensors", "缺少模型文件"),
     "模型文件缺失", "请先在设置页下载 BiRefNet 模型"),

    # Filesystem
    (FileNotFoundError, "找不到文件: {msg}", "请检查路径是否正确"),
    (PermissionError, "没有权限访问: {msg}", "请检查文件权限或以管理员身份运行"),

    # Network
    (_has("connection", "timeout", "network"),
     "网络请求失败", "请检查网络连接后重试"),
]


def user_message(exc: Exception) -> tuple[str, str]:
    """Return (msg, hint). Falls back to '<Type>: <raw>' / '查看日志了解详情'."""
    for matcher, msg_tpl, hint in ERROR_PATTERNS:
        matched = (
            isinstance(matcher, type) and isinstance(exc, matcher)
        ) or (
            callable(matcher) and not isinstance(matcher, type) and matcher(exc)
        )
        if matched:
            return msg_tpl.format(msg=str(exc)), hint

    return f"{type(exc).__name__}: {exc}", "查看日志了解详情"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_errors.py -v
```
Expected: 10 PASSED.

- [ ] **Step 5: Commit**

```bash
git add core/errors.py tests/test_errors.py
git commit -m "$(cat <<'EOF'
refactor: 抽离 core/errors 翻译异常为友好中文文案

- ERROR_PATTERNS 表覆盖：API Key/限流/配额/安全过滤/OOM/模型缺失/文件/网络
- 未匹配回退到「类型: 原文」+ 「查看日志」提示
- 首匹配生效，顺序敏感

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: core/skills.py

**Files:**
- Create: `core/skills.py`
- Create: `tests/test_skills.py`

- [ ] **Step 1: 写测试**

Write `tests/test_skills.py`:
```python
"""Tests for core.skills — skill script loader."""
from pathlib import Path

import pytest

from core import skills


def test_load_known_skill_returns_module(monkeypatch):
    # We assume tests run from repo root
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root)

    mod = skills.load("rmbg")
    assert hasattr(mod, "load_model")
    assert hasattr(mod, "process_image")


def test_load_caches_module():
    a = skills.load("bwdiff")
    b = skills.load("bwdiff")
    assert a is b


def test_load_unknown_skill_raises():
    with pytest.raises(KeyError, match="unknown skill"):
        skills.load("nonexistent")


def test_all_known_skills_loadable():
    for name in ["rmbg", "bwdiff", "bwgen", "gen-image"]:
        mod = skills.load(name)
        assert mod is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_skills.py -v
```
Expected: 4 FAIL.

- [ ] **Step 3: 写实现**

Write `core/skills.py`:
```python
"""Lazy-loader for the skill scripts under .claude/skills/<name>/scripts/.

Each skill's primary script is loaded once and cached. Replaces the
ad-hoc importlib dance previously inlined in app.py.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent

# skill_name -> (relative script path under .claude/skills/<name>/scripts/, module name)
SKILL_SCRIPTS: dict[str, tuple[str, str]] = {
    "rmbg": ("rmbg/scripts/rmbg_process.py", "rmbg_process"),
    "bwdiff": ("bwdiff/scripts/bw_diff.py", "bw_diff"),
    "bwgen": ("bwgen/scripts/bw_gen.py", "bw_gen"),
    "gen-image": ("gen-image/scripts/gen_image.py", "gen_image"),
}

_cache: dict[str, ModuleType] = {}


def load(name: str) -> ModuleType:
    """Load and cache a skill script module. Raises KeyError for unknown name."""
    if name in _cache:
        return _cache[name]

    if name not in SKILL_SCRIPTS:
        raise KeyError(f"unknown skill: {name}")

    rel_path, mod_name = SKILL_SCRIPTS[name]
    full_path = REPO_ROOT / ".claude" / "skills" / rel_path

    spec = importlib.util.spec_from_file_location(mod_name, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load skill {name} at {full_path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _cache[name] = mod
    return mod
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_skills.py -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add core/skills.py tests/test_skills.py
git commit -m "$(cat <<'EOF'
refactor: 抽离 core/skills 作为 skill 脚本加载器

- SKILL_SCRIPTS 表显式列出 4 个 skill 的脚本路径，无字符串拼接
- 模块级 _cache 单例，避免重复 exec_module
- 取代 app.py 中的 _load_module 反射调用

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: core/state.py（模型懒加载单例）

**Files:**
- Create: `core/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: 写测试**

Write `tests/test_state.py`:
```python
"""Tests for core.state.ModelRegistry — lazy singleton with concurrency lock."""
import threading
from unittest.mock import MagicMock

import pytest

from core import state


def test_registry_calls_loader_once():
    registry = state.ModelRegistry()
    loader = MagicMock(return_value=("model_obj", "cpu"))

    a = registry.get_or_load("rmbg", loader, model_dir="/x")
    b = registry.get_or_load("rmbg", loader, model_dir="/x")

    assert a == ("model_obj", "cpu")
    assert b == ("model_obj", "cpu")
    loader.assert_called_once_with(model_dir="/x")


def test_registry_different_keys_independent():
    registry = state.ModelRegistry()
    loader_a = MagicMock(return_value=("A", "cpu"))
    loader_b = MagicMock(return_value=("B", "cpu"))

    a = registry.get_or_load("a", loader_a)
    b = registry.get_or_load("b", loader_b)

    assert a[0] == "A"
    assert b[0] == "B"


def test_registry_concurrent_load_calls_loader_once():
    """Two threads racing to first-load the same key should call loader exactly once."""
    registry = state.ModelRegistry()
    call_count = [0]
    barrier = threading.Barrier(2)

    def slow_loader():
        barrier.wait()  # Force both threads to enter together
        call_count[0] += 1
        return ("x", "cpu")

    results = []
    def worker():
        results.append(registry.get_or_load("k", slow_loader))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert call_count[0] == 1
    assert results[0] == results[1]


def test_registry_clear():
    registry = state.ModelRegistry()
    loader = MagicMock(return_value=("x", "cpu"))

    registry.get_or_load("k", loader)
    registry.clear()
    registry.get_or_load("k", loader)

    assert loader.call_count == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_state.py -v
```
Expected: 4 FAIL.

- [ ] **Step 3: 写实现**

Write `core/state.py`:
```python
"""Cross-session shared state.

Currently: ModelRegistry — a thread-safe lazy-loaded singleton holder for
heavy ML models (BiRefNet ~840MB). Per-user state lives in gr.State, not here.
"""
import threading
from typing import Any, Callable


class ModelRegistry:
    """Lazy-load heavy models once, keep them across all sessions.

    Per-key lock prevents two concurrent first-loads from racing.
    """

    def __init__(self):
        self._models: dict[str, Any] = {}
        self._global_lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}

    def _lock_for(self, key: str) -> threading.Lock:
        with self._global_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def get_or_load(self, key: str, loader: Callable, **loader_kwargs) -> Any:
        """Return cached value for key, calling loader(**kwargs) on first access."""
        if key in self._models:
            return self._models[key]

        with self._lock_for(key):
            # Double-check after acquiring lock
            if key in self._models:
                return self._models[key]
            value = loader(**loader_kwargs)
            self._models[key] = value
            return value

    def clear(self) -> None:
        """Drop all cached models. Useful for tests or model-dir change."""
        with self._global_lock:
            self._models.clear()


# Module-level singleton
registry = ModelRegistry()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_state.py -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add core/state.py tests/test_state.py
git commit -m "$(cat <<'EOF'
refactor: 抽离 core/state.ModelRegistry 处理重型模型的全局缓存

- 跨 session 共享模型实例（BiRefNet ~840MB，per-session 加载会爆内存）
- 双检锁 + 每 key 独立 lock，防止并发首次加载竞争
- 取代 app.py 中的 _loaded_model / _loaded_device 模块级全局变量

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: core/history.py

**Files:**
- Create: `core/history.py`
- Create: `tests/test_history.py`

- [ ] **Step 1: 写测试**

Write `tests/test_history.py`:
```python
"""Tests for core.history — JSON read/write, atomic, thread-safe, thumbnail."""
import json
import threading
from pathlib import Path

import pytest
from PIL import Image

from core import history


def _sample_entry(typ="rmbg") -> dict:
    return {
        "id": "20260509_120000_aaaa",
        "timestamp": "2026-05-09T12:00:00",
        "type": typ,
        "input": {"image_path": "x.png", "params": {"threshold": 0.5}},
        "output": {"image_path": "y.png", "extra_paths": None},
        "thumb_path": "z.webp",
        "prompt": None,
        "model": None,
    }


def test_load_returns_empty_when_missing(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    assert store.load() == []


def test_append_and_load(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    e = _sample_entry()
    store.append(e)
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0]["id"] == e["id"]


def test_filter_by_type(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    store.append(_sample_entry("rmbg"))
    e2 = _sample_entry("bwgen")
    e2["id"] = "different"
    store.append(e2)

    rmbg_only = store.filter("rmbg")
    assert len(rmbg_only) == 1
    assert rmbg_only[0]["type"] == "rmbg"

    abstract = store.filter("抠图")  # group: rmbg + bwdiff
    assert len(abstract) == 1
    assert abstract[0]["type"] == "rmbg"


def test_clear_removes_entries_and_thumbs(tmp_project):
    thumb_dir = tmp_project / "local" / "output" / ".thumbs"
    thumb_dir.mkdir(parents=True)
    (thumb_dir / "z.webp").write_bytes(b"fake")

    store = history.HistoryStore(tmp_project / "local" / "history.json", thumb_dir=thumb_dir)
    store.append(_sample_entry())

    store.clear()

    assert store.load() == []
    assert not (thumb_dir / "z.webp").exists()


def test_concurrent_appends(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    barrier = threading.Barrier(5)

    def worker(i):
        barrier.wait()
        e = _sample_entry()
        e["id"] = f"id-{i}"
        store.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()

    loaded = store.load()
    assert len(loaded) == 5
    assert {e["id"] for e in loaded} == {f"id-{i}" for i in range(5)}


def test_make_thumbnail(tmp_project):
    img = Image.new("RGB", (512, 256), (255, 0, 0))
    src = tmp_project / "src.png"
    img.save(src)

    thumb_dir = tmp_project / "local" / "output" / ".thumbs"
    thumb_path = history.make_thumbnail(src, thumb_dir, "test_id")

    assert thumb_path.exists()
    assert thumb_path.suffix == ".webp"
    thumb = Image.open(thumb_path)
    assert max(thumb.size) <= 128


def test_corrupt_file_recovers_via_backup(tmp_project):
    history_path = tmp_project / "local" / "history.json"
    history_path.parent.mkdir()
    history_path.write_text("{not json", encoding="utf-8")

    store = history.HistoryStore(history_path,
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    assert store.load() == []
    assert (tmp_project / "local" / "history.json.bak").exists()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_history.py -v
```
Expected: 7 FAIL.

- [ ] **Step 3: 写实现**

Write `core/history.py`:
```python
"""Persistent history of image processing operations.

JSON file at local/history.json, schema:
    {"version": 1, "entries": [HistoryEntry, ...]}

Each HistoryEntry:
    id: timestamp + 4 hex chars
    timestamp: ISO 8601
    type: rmbg | bwdiff | bwgen | gen | pipeline
    input: {image_path, params}
    output: {image_path, extra_paths}
    thumb_path: path to 128px webp thumbnail
    prompt, model: optional (filled for bwgen/gen/pipeline)

Thread-safe append via threading.Lock + atomic write.
Corrupt files are backed up to .bak and replaced with empty.
"""
import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image

SCHEMA_VERSION = 1
THUMB_MAX = 128

# UI filter chips → set of types
TYPE_GROUPS = {
    "all": {"rmbg", "bwdiff", "bwgen", "gen", "pipeline"},
    "抠图": {"rmbg", "bwdiff"},
    "生图": {"bwgen", "gen"},
    "流程": {"pipeline"},
}


def make_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"


def make_thumbnail(src: Path, thumb_dir: Path, entry_id: str) -> Path:
    """Generate a 128px webp thumbnail. Returns the thumbnail path."""
    thumb_dir = Path(thumb_dir)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{entry_id}.webp"

    img = Image.open(src)
    img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    # webp doesn't accept palette modes
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    img.save(thumb_path, "WEBP", quality=85)
    return thumb_path


class HistoryStore:
    """Thread-safe persistent history."""

    def __init__(self, json_path: Path, thumb_dir: Path):
        self.json_path = Path(json_path)
        self.thumb_dir = Path(thumb_dir)
        self._lock = threading.Lock()

    def load(self) -> list[dict]:
        """Return all entries; empty list if file missing or corrupt."""
        if not self.json_path.is_file():
            return []
        try:
            with open(self.json_path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("entries", [])
        except (json.JSONDecodeError, OSError):
            # Backup the corrupt file so user can inspect it later
            backup = self.json_path.with_suffix(self.json_path.suffix + ".bak")
            shutil.copy2(self.json_path, backup)
            return []

    def _write(self, entries: list[dict]) -> None:
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.json_path.with_suffix(self.json_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": SCHEMA_VERSION, "entries": entries},
                      f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.json_path)

    def append(self, entry: dict) -> None:
        """Append one entry. Thread-safe."""
        with self._lock:
            entries = self.load()
            entries.append(entry)
            self._write(entries)

    def filter(self, group: str) -> list[dict]:
        """Filter entries by group name from TYPE_GROUPS."""
        types = TYPE_GROUPS.get(group, TYPE_GROUPS["all"])
        return [e for e in self.load() if e.get("type") in types]

    def clear(self) -> None:
        """Drop all entries and delete all thumbnails. Original outputs untouched."""
        with self._lock:
            entries = self.load()
            for e in entries:
                tp = e.get("thumb_path")
                if tp:
                    p = Path(tp)
                    if not p.is_absolute():
                        p = self.thumb_dir.parent.parent / p
                    if p.is_file():
                        try:
                            p.unlink()
                        except OSError:
                            pass
            self._write([])
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_history.py -v
```
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add core/history.py tests/test_history.py
git commit -m "$(cat <<'EOF'
feat: 新增 core/history 持久化历史记录

- HistoryStore: JSON 原子写、threading.Lock 保护并发 append
- TYPE_GROUPS: 抠图/生图/流程 三种过滤聚合
- make_thumbnail: 128px webp，存于 local/output/.thumbs/
- 损坏的 history.json 自动备份为 .bak 后重建
- 不限条数，clear() 仅删 entries 与缩略图，不动原始输出

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 重构 app.py 使用 core/ 模块（保留现有 UI）

**Files:**
- Modify: `app.py`

> 此任务不动 UI 行为，只把现有 `_load_config / _save_config / get_config_value / get_model / _load_module / 三处 API key 处理` 替换为 `core/` 调用。

- [ ] **Step 1: 替换 imports 和模块加载**

Edit `app.py:1-35`:
```python
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
```

Delete `app.py:22-34` (`_load_module` and the per-skill `_load_module(...)` calls — already done above).

- [ ] **Step 2: 替换 config helpers (app.py:36-71)**

Edit to:
```python
# ── Config helpers ────────────────────────────────────────────────────────────

CONFIG_PATH = PROJECT_DIR / "local" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_config():
    return cfg_mod.load(CONFIG_PATH)


def _save_config(data):
    cfg_mod.save(CONFIG_PATH, data)


def get_config_value(key, env_var=None):
    return cfg_mod.get_value(CONFIG_PATH, key, env_var=env_var,
                             default=cfg_mod.DEFAULTS.get(key, ""))


# Default model_dir is computed once
DEFAULT_MODEL_DIR = str(PROJECT_DIR / "local" / "models" / "RMBG-2.0")
```

Replace existing `DEFAULT_CONFIG = {...}` references in the rest of the file:
- `DEFAULT_CONFIG["model_dir"]` → `DEFAULT_MODEL_DIR`

- [ ] **Step 3: 替换模型缓存为 core.state.registry (app.py:73-84)**

Edit to:
```python
# ── Shared state ──────────────────────────────────────────────────────────────


def get_model(model_dir):
    return state.registry.get_or_load(
        f"rmbg::{model_dir}",
        rmbg_mod.load_model,
        model_dir=model_dir,
    )


def _make_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")
```

- [ ] **Step 4: 替换三处 API Key 处理 — bwgen_generate (app.py:173-198)**

Edit `bwgen_generate`:
```python
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
```

- [ ] **Step 5: 替换三处 API Key 处理 — genimg_generate (app.py:203-224)**

Edit `genimg_generate`:
```python
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
```

- [ ] **Step 6: 重写 pipeline_run 复用 bwgen + bwdiff（不复制代码） (app.py:229-263)**

Edit `pipeline_run`:
```python
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

        # Step 2: diff to RGBA (reuses bwdiff module)
        result = bwdiff_mod.bw_diff(black_path, white_path)

        from PIL import Image
        return (Image.open(black_path), Image.open(white_path), result,
                f"管线完成 ✓\n{black_path}\n{white_path}")
    except api_keys.MissingKey as e:
        return None, None, None, str(e)
    except Exception as e:
        msg, hint = errors.user_message(e)
        return None, None, None, f"{msg}\n{hint}"
```

- [ ] **Step 7: 修复 bwdiff 全局变量 bug — 改用 gr.State (app.py:135-168)**

Find the bwdiff Tab section (`with gr.Tab("⬛⬜ 黑白差分"):`) and replace its handlers. Delete `_TMP_BLACK / _TMP_WHITE / bwdiff_cache_black / bwdiff_cache_white / bwdiff_process` definitions; replace the Tab body with:

```python
    with gr.Tab("⬛⬜ 黑白差分"):
        gr.Markdown("### 黑白差分去背景（需同机位黑底+白底图）")
        with gr.Row():
            with gr.Column(scale=1):
                bwdiff_black = gr.Image(label="黑底图", type="pil", height=250)
            with gr.Column(scale=1):
                bwdiff_white = gr.Image(label="白底图", type="pil", height=250)
            with gr.Column(scale=1):
                bwdiff_result = gr.Image(label="抠图结果", type="pil", height=250,
                                         format="png", image_mode="RGBA",
                                         buttons=["fullscreen"])
        with gr.Row():
            bwdiff_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
        bwdiff_status = gr.Textbox(label="状态", interactive=False)

        def _bwdiff_process(black, white):
            if black is None or white is None:
                return None, "请上传黑底图和白底图"
            if black.size != white.size:
                return None, f"两张图片尺寸不一致（黑: {black.size}，白: {white.size}）"
            try:
                import numpy as np
                from PIL import Image
                ba = np.array(black.convert("RGB"), dtype=np.float32)
                wa = np.array(white.convert("RGB"), dtype=np.float32)
                alpha, fg = bwdiff_mod.compute_alpha(ba, wa)
                return Image.fromarray(np.dstack([fg, alpha]), "RGBA"), "处理完成 ✓"
            except Exception as e:
                msg, hint = errors.user_message(e)
                return None, f"{msg}\n{hint}"

        bwdiff_btn.click(
            fn=_bwdiff_process,
            inputs=[bwdiff_black, bwdiff_white],
            outputs=[bwdiff_result, bwdiff_status],
        )
```

> 关键变化：参数直接从 `gr.Image` 输入（per-session），不再依赖模块级 `_TMP_BLACK/_TMP_WHITE`。

- [ ] **Step 8: 删除残留的 dead code**

Search for `_TMP_BLACK`, `_TMP_WHITE`, `bwdiff_cache_black`, `bwdiff_cache_white`, `_loaded_model`, `_loaded_device`, `DEFAULT_CONFIG` — confirm none remain.

```bash
grep -nE "_TMP_BLACK|_TMP_WHITE|bwdiff_cache|_loaded_model|_loaded_device|DEFAULT_CONFIG" app.py
```
Expected: no matches.

- [ ] **Step 9: 启动验证（手动）**

```bash
python app.py
```
打开 http://127.0.0.1:7861 验证：
- 6 个 Tab 全部可见
- 设置页能保存 API Key
- 上传图到「去背景」能处理（如本地有 BiRefNet 模型）
- 「黑白差分」上传两张图能处理
- 「生黑白底」/「生图」（如配了 Key）能调用
- 「一键管线」能运行

按 Ctrl+C 终止。

- [ ] **Step 10: 跑测试套件**

```bash
pytest tests/ -v
```
Expected: 33 PASSED（前 6 个 Task 累计）。

- [ ] **Step 11: Commit**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
refactor: app.py 切换到 core/ 模块，UI 行为不变

- _load_config/_save_config/get_config_value → core.config
- _load_module → core.skills.load
- 模型缓存 _loaded_model → core.state.registry
- 三处 API Key 处理 → with api_keys.use_api_key(...)
- 异常 → core.errors.user_message 翻译为中文
- 修复 bwdiff 多标签 bug：上传缓存改为 gr.Image 输入参数（per-session）
- pipeline_run 改为调用 bwgen.generate_black_white + bwdiff.bw_diff，不再复制代码

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: PR 1 收尾 — 更新文档与提交 PR

**Files:**
- Modify: `.claude/CLAUDE.md`

- [ ] **Step 1: 在 CLAUDE.md「目录结构」一节追加 `core/` 与 `tests/` 说明**

Insert after the `.claude/skills/` block in the directory tree section:
```
core/                     # 纯逻辑模块（无 Gradio 依赖）
  config.py               # 配置文件读写 + DEFAULTS
  api_keys.py             # API Key 解析 + use_api_key 上下文
  errors.py               # 异常 → 中文友好文案
  skills.py               # skill 脚本懒加载 + 缓存
  state.py                # ModelRegistry 全局模型单例
  history.py              # 历史 JSON 读写 + 缩略图（Task 7 加入）
tests/                    # pytest 单元测试
  conftest.py
  test_*.py
```

- [ ] **Step 2: Commit 文档**

```bash
git add .claude/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: CLAUDE.md 同步 core/ 与 tests/ 目录

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: 创建 PR 1**

```bash
git push -u origin <feature-branch-name>
gh pr create --title "PR 1 · 后端重构（core/ 模块化 + 测试）" --body "$(cat <<'EOF'
## Summary
- 抽离 `core/` 模块：config / api_keys / errors / skills / state / history
- 修复 bwdiff 多标签上传缓存竞争 bug
- pipeline 复用 bwgen + bwdiff，不再复制代码
- 新增 pytest 测试套件（33 用例覆盖纯逻辑）
- UI 行为不变，下一 PR 重写

## Test plan
- [ ] `pytest tests/ -v` 全绿
- [ ] `python app.py` 6 个 Tab 功能与重构前一致
- [ ] 多浏览器标签同时上传 bwdiff 互不干扰
- [ ] 模型只在第一次使用时加载，后续 session 复用

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# PR 2 · UI 重写（依赖 PR 1）

> 假设 PR 1 已合并到 main。此 PR 大量新建 `ui/` 模块，重写 `app.py` 为薄壳。

## Task 10: ui/theme.py — CSS 变量与主题切换

**Files:**
- Create: `ui/__init__.py`
- Create: `ui/theme.py`

- [ ] **Step 1: 写 ui 包占位**

Write `ui/__init__.py`:
```python
"""Gradio UI assembly modules."""
```

- [ ] **Step 2: 写 theme.py**

Write `ui/theme.py`:
```python
"""CSS variables, light/dark theme toggle.

The theme toggle works by adding a `data-theme=dark` attribute on <body>.
CSS variables under :root and [data-theme=dark] override base palette.
"""
import gradio as gr

CSS = """
:root {
  --primary: #6366f1;
  --primary-grad: linear-gradient(135deg, #6366f1, #8b5cf6);
  --bg: #f7f8fa;
  --surface: #ffffff;
  --border: #ebeef3;
  --text: #1f2937;
  --text-mute: #6b7280;
  --success: #059669;
  --warn: #b45309;
  --error: #dc2626;
}
body[data-theme=dark] {
  --bg: #0f1117;
  --surface: #1a1d27;
  --border: #2a2f3d;
  --text: #e5e7eb;
  --text-mute: #9ca3af;
}

/* Layout */
.gradio-container { background: var(--bg) !important; color: var(--text) !important; }

#topbar {
  position: sticky; top: 0; z-index: 50;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 12px 20px;
  display: flex; justify-content: space-between; align-items: center;
}
#topbar .title { font-weight: 700; font-size: 15px; color: var(--text); }
#topbar .badges { display: flex; gap: 8px; align-items: center; }
.badge {
  padding: 3px 10px; border-radius: 12px;
  font-size: 11px; font-weight: 600;
}
.badge.ok { background: #ecfdf5; color: var(--success); }
.badge.warn { background: #fef3c7; color: var(--warn); }
body[data-theme=dark] .badge.ok { background: #064e3b; color: #6ee7b7; }
body[data-theme=dark] .badge.warn { background: #78350f; color: #fcd34d; }

#sidebar {
  background: var(--surface) !important;
  border-right: 1px solid var(--border);
  min-width: 200px; max-width: 200px;
}
.sidebar-section { padding: 10px 12px 4px; font-size: 9px; color: var(--text-mute);
  text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; }
.sidebar-item { padding: 8px 12px; font-size: 13px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; gap: 9px; color: var(--text); }
.sidebar-item:hover { background: var(--bg); }
.sidebar-item.active {
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  color: #4338ca; font-weight: 600;
}
body[data-theme=dark] .sidebar-item.active {
  background: linear-gradient(135deg, #312e81, #4c1d95); color: #c7d2fe;
}

#history {
  background: var(--surface) !important;
  border-left: 1px solid var(--border);
  min-width: 220px; max-width: 220px;
  padding: 14px 12px;
}

.gr-button.primary, button.gr-button-primary {
  background: var(--primary-grad) !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(99,102,241,0.25) !important;
}
"""

# JavaScript that toggles data-theme attribute and persists to backend
THEME_TOGGLE_JS = """
function toggleTheme() {
    const cur = document.body.getAttribute('data-theme') || 'light';
    const next = cur === 'light' ? 'dark' : 'light';
    document.body.setAttribute('data-theme', next);
    return next;
}
"""

THEME_INIT_JS = """
function initTheme(theme) {
    document.body.setAttribute('data-theme', theme || 'light');
    return theme;
}
"""


def soft_theme() -> gr.themes.Soft:
    """Gradio Soft theme tweaked to harmonize with our CSS variables."""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.indigo,
        secondary_hue=gr.themes.colors.violet,
    )
```

- [ ] **Step 3: 跑测试套件确保未破坏**

```bash
pytest tests/ -v
```
Expected: 33 PASSED.

- [ ] **Step 4: Commit**

```bash
git add ui/__init__.py ui/theme.py
git commit -m "$(cat <<'EOF'
feat(ui): theme.py — CSS 变量、亮/暗主题切换

- :root / body[data-theme=dark] 提供两套色板
- Topbar / sidebar / history 容器样式
- 紫蓝渐变主按钮
- toggleTheme/initTheme JS 由 app.py 串联到 gr.State

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: ui/tooltips.py — 集中提示文案

**Files:**
- Create: `ui/tooltips.py`
- Create: `tests/test_tooltips.py`

- [ ] **Step 1: 写测试**

Write `tests/test_tooltips.py`:
```python
"""Tests for ui.tooltips — every key referenced from views must exist."""
import pytest

from ui import tooltips


REQUIRED_KEYS = [
    "rmbg.threshold", "rmbg.edge_refine", "rmbg.white_bg", "rmbg.upload",
    "bwdiff.upload_black", "bwdiff.upload_white",
    "bwgen.prompt", "bwgen.ratio", "bwgen.size", "bwgen.model",
    "gen.prompt", "gen.ratio", "gen.size", "gen.model",
    "pipeline.prompt",
    "settings.gemini_key", "settings.dashscope_key", "settings.model_dir",
    "settings.theme",
]


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_key_exists(key):
    assert tooltips.get(key) != ""


def test_unknown_key_returns_empty():
    assert tooltips.get("nonexistent.key") == ""


def test_get_for_returns_dict_section():
    rmbg = tooltips.get_for("rmbg")
    assert "threshold" in rmbg
    assert "edge_refine" in rmbg
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_tooltips.py -v
```
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

Write `ui/tooltips.py`:
```python
"""All tooltip text in one place. Looked up by dotted key.

Used by gr.Slider(info=...), gr.Checkbox(info=...), etc.
Keep messages short — Gradio renders these next to the control.
"""

TOOLTIPS: dict[str, str] = {
    # rmbg
    "rmbg.upload": "支持 PNG / JPG / WebP，建议 < 50MB。复杂边缘图建议开启「边缘优化」。",
    "rmbg.threshold": "0.3-0.4 保留更多发丝/绒毛细节；0.5 平衡；0.6-0.7 边缘更干净但可能丢失细节。",
    "rmbg.edge_refine": "对 mask 边缘做高斯平滑，避免锯齿。处理时间增加约 10%。",
    "rmbg.white_bg": "勾选后输出白色背景的 RGB 图（非透明 PNG），适合直接打印。",

    # bwdiff
    "bwdiff.upload_black": "黑底图：与白底图同机位、同光照、同分辨率拍摄。",
    "bwdiff.upload_white": "白底图：与黑底图同机位、同光照、同分辨率拍摄。",

    # bwgen
    "bwgen.prompt": "描述主体即可，无需提到背景。系统会自动添加「placed on solid black/white background」。",
    "bwgen.ratio": "1:1 通用；16:9 横屏；9:16 手机壁纸；3:4 / 4:3 接近 A4。",
    "bwgen.size": "1K=1024px 长边；2K=2048px；4K 仅 Wan2.7 文生图支持，速度慢 2-4 倍。",
    "bwgen.model": "Gemini 速度快，DashScope (Wan2.7) 质量更高且支持 4K。",

    # gen-image
    "gen.prompt": "英文效果通常更好。可包含风格、光照、镜头等修饰词。",
    "gen.ratio": "1:1 通用；16:9 横屏壁纸；9:16 手机壁纸。",
    "gen.size": "1K=1024px 长边；2K=2048px；4K 仅 Wan2.7 支持。",
    "gen.model": "Gemini 速度快，Wan2.7 质量更高。",

    # pipeline
    "pipeline.prompt": "一次性完成「生黑白底图 → 差分抠图」。出错率比单纯 AI 抠图低。",

    # settings
    "settings.gemini_key": "用于 Gemini 图片生成（gen-image、bwgen）。在 https://aistudio.google.com 申请。",
    "settings.dashscope_key": "用于阿里云百炼 Wan2.7 Pro 图片生成。在 https://dashscope.console.aliyun.com 申请。",
    "settings.model_dir": "BiRefNet 深度学习去背景模型所在目录。需包含 model.safetensors。",
    "settings.theme": "亮色 / 暗色界面切换。下次启动会记住选择。",
}


def get(key: str) -> str:
    """Return tooltip text or empty string if key unknown."""
    return TOOLTIPS.get(key, "")


def get_for(prefix: str) -> dict[str, str]:
    """Return all tooltips under a dotted prefix, with prefix stripped from keys."""
    p = prefix + "."
    return {k[len(p):]: v for k, v in TOOLTIPS.items() if k.startswith(p)}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/test_tooltips.py -v
```
Expected: 21 PASSED.

- [ ] **Step 5: Commit**

```bash
git add ui/tooltips.py tests/test_tooltips.py
git commit -m "$(cat <<'EOF'
feat(ui): tooltips.py 集中所有控件提示文案

- 19 条覆盖 6 个 view 全部参数
- get(dotted_key) / get_for(prefix) 两种取用方式
- 测试用 REQUIRED_KEYS 列表保证 view 引用的 key 不会缺失

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: ui/toast.py — Toast 通知封装

**Files:**
- Create: `ui/toast.py`

- [ ] **Step 1: 写实现**

Write `ui/toast.py`:
```python
"""Thin wrapper around Gradio 5.x gr.Info / gr.Warning / gr.Error.

Centralizes the "raise to user" pattern so views don't need to import gr
just for notifications. Also formats (msg, hint) tuples from core.errors.
"""
import gradio as gr


def success(msg: str) -> None:
    """Green toast, auto-dismisses."""
    gr.Info(msg)


def warn(msg: str) -> None:
    """Yellow toast, auto-dismisses."""
    gr.Warning(msg)


def error(msg: str, hint: str = "") -> None:
    """Red toast, requires manual dismissal. Renders hint on its own line."""
    text = f"{msg}\n💡 {hint}" if hint else msg
    raise gr.Error(text)


def from_exception(exc: Exception) -> None:
    """Translate via core.errors and raise as toast."""
    from core import errors
    msg, hint = errors.user_message(exc)
    error(msg, hint)
```

- [ ] **Step 2: Commit**

```bash
git add ui/toast.py
git commit -m "$(cat <<'EOF'
feat(ui): toast.py 封装 Toast 通知

- success/warn/error 对应 gr.Info/Warning/Error
- from_exception 调 core.errors 翻译后弹 Toast
- 错误 Toast 显示「msg + 💡 hint」两行，需手动关闭

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: ui/views/ 包 + settings view

**Files:**
- Create: `ui/views/__init__.py`
- Create: `ui/views/settings.py`

- [ ] **Step 1: 写 settings view**

Write `ui/views/__init__.py`:
```python
"""Per-view modules. Each exports a build(state) function returning a gr.Group."""
```

Write `ui/views/settings.py`:
```python
"""Settings view — API keys, model dir, theme."""
from pathlib import Path

import gradio as gr

from core import api_keys, config as cfg
from ui import tooltips, toast


def _badge_html(label: str, ok: bool) -> str:
    cls = "ok" if ok else "warn"
    icon = "🔑" if ok else "❌"
    text = "已配置" if ok else "未配置"
    return f'<span class="badge {cls}">{icon} {label} {text}</span>'


def build(config_path: Path, default_model_dir: str):
    """Return (group, refresh_badges_fn). Group is hidden by default."""
    with gr.Group(visible=False, elem_id="view-settings") as group:
        gr.Markdown("## ⚙ 设置")
        gr.Markdown(
            "💡 配置保存到 `local/config.json`，下次自动加载。"
            " API Key 已配置时显示「🔑 已配置」，留空字段不会清除已有值。"
        )

        initial = cfg.load(config_path)

        with gr.Row():
            gemini_key = gr.Textbox(
                label="Gemini API Key", type="password",
                placeholder="留空不修改", info=tooltips.get("settings.gemini_key"),
            )
        with gr.Row():
            dashscope_key = gr.Textbox(
                label="DashScope API Key", type="password",
                placeholder="留空不修改", info=tooltips.get("settings.dashscope_key"),
            )

        gr.Markdown("### 模型路径")
        model_dir_input = gr.Textbox(
            label="BiRefNet 模型目录",
            value=initial.get("model_dir", default_model_dir),
            info=tooltips.get("settings.model_dir"),
        )

        gr.Markdown("### 默认偏好")
        with gr.Row():
            default_model = gr.Dropdown(
                label="默认模型", choices=["gemini", "wan"],
                value=initial.get("default_model", "gemini"),
            )
            default_ratio = gr.Dropdown(
                label="默认宽高比",
                choices=["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"],
                value=initial.get("default_ratio", "1:1"),
            )
            default_size = gr.Dropdown(
                label="默认分辨率",
                choices=["512", "1K", "2K", "4K"],
                value=initial.get("default_size", "1K"),
            )

        save_btn = gr.Button("💾 保存设置", variant="primary", size="lg")

        def _save(gem, ds, mdir, dm, dr, ds_size):
            try:
                cfg.update(config_path,
                           gemini_api_key=gem.strip() if gem else None,
                           dashscope_api_key=ds.strip() if ds else None,
                           model_dir=mdir.strip() if mdir else None,
                           default_model=dm, default_ratio=dr, default_size=ds_size)
                toast.success("设置已保存 ✓")
            except Exception as e:
                toast.from_exception(e)

        save_btn.click(
            fn=_save,
            inputs=[gemini_key, dashscope_key, model_dir_input,
                    default_model, default_ratio, default_size],
        )

    return group


def badges_html(config_path: Path) -> str:
    """Build the topbar badges HTML for current state."""
    import torch
    gpu_ok = torch.cuda.is_available()
    gpu_label = "GPU" if gpu_ok else "CPU"
    gpu_cls = "ok" if gpu_ok else "warn"

    has_gemini = bool(api_keys.resolve(config_path, "gemini"))
    has_wan = bool(api_keys.resolve(config_path, "wan"))

    return (
        f'<span class="badge {gpu_cls}">🖥 {gpu_label}</span>'
        + _badge_html("Gemini", has_gemini)
        + _badge_html("DashScope", has_wan)
    )
```

- [ ] **Step 2: Commit**

```bash
git add ui/views/__init__.py ui/views/settings.py
git commit -m "$(cat <<'EOF'
feat(ui/views): settings view + topbar badges builder

- 三组配置：API Keys / 模型路径 / 默认偏好（model/ratio/size）
- Toast 反馈保存结果
- badges_html 渲染顶栏 GPU + 两个 Key 的状态徽章

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: ui/views/rmbg.py

**Files:**
- Create: `ui/views/rmbg.py`

- [ ] **Step 1: 写 rmbg view**

Write `ui/views/rmbg.py`:
```python
"""Smart background removal view (BiRefNet)."""
from pathlib import Path

import gradio as gr

from core import errors, skills, state
from ui import tooltips, toast


def build(config_path: Path, default_model_dir: str):
    """Return the gr.Group for this view."""
    rmbg_mod = skills.load("rmbg")

    with gr.Group(visible=True, elem_id="view-rmbg") as group:
        gr.Markdown("## 🎯 智能去背景")
        gr.Markdown("基于 BiRefNet 深度学习模型，支持 GPU 加速。"
                    "💡 适合人像、宠物、产品；复杂边缘建议开启「边缘优化」。")

        with gr.Row():
            with gr.Column(scale=1):
                input_img = gr.Image(label="上传图片", type="pil", height=300,
                                     sources=["upload", "clipboard"],
                                     image_mode="RGB")
                gr.Markdown(f"<small>{tooltips.get('rmbg.upload')}</small>")

                threshold = gr.Slider(
                    label="二值化阈值",
                    minimum=0.3, maximum=0.7, value=0.5, step=0.05,
                    info=tooltips.get("rmbg.threshold"),
                )
                with gr.Row():
                    edge_refine = gr.Checkbox(label="边缘优化", value=True,
                                              info=tooltips.get("rmbg.edge_refine"))
                    white_bg = gr.Checkbox(label="白底输出", value=False,
                                           info=tooltips.get("rmbg.white_bg"))

                run_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")

            with gr.Column(scale=1):
                output_img = gr.Image(label="结果", type="pil", height=400,
                                      format="png", image_mode="RGBA",
                                      buttons=["fullscreen"])

        def _process(image, thresh, edge, white, progress=gr.Progress()):
            if image is None:
                toast.warn("请上传图片")
                return None
            from core import config as cfg
            mdir = cfg.get_value(config_path, "model_dir", default=default_model_dir)
            if not Path(mdir).is_dir():
                toast.error("模型目录不存在", "请到「设置」配置 BiRefNet 模型路径")
                return None

            try:
                progress(0.1, desc="加载模型...")
                model, device = state.registry.get_or_load(
                    f"rmbg::{mdir}", rmbg_mod.load_model, model_dir=mdir,
                )
                progress(0.5, desc="推理中...")
                result = rmbg_mod.process_image(
                    image, model, device,
                    threshold=thresh, edge_refine=edge, white_bg=white,
                )
                progress(1.0, desc="完成")
                toast.success("处理完成 ✓")
                return result
            except Exception as e:
                toast.from_exception(e)
                return None

        run_btn.click(
            fn=_process,
            inputs=[input_img, threshold, edge_refine, white_bg],
            outputs=[output_img],
        )

        # Expose components for history refill
        group.refill_targets = {
            "input_image": input_img,
            "threshold": threshold,
            "edge_refine": edge_refine,
            "white_bg": white_bg,
        }

    return group
```

- [ ] **Step 2: Commit**

```bash
git add ui/views/rmbg.py
git commit -m "feat(ui/views): rmbg view 重写为独立模块

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: ui/views/bwdiff.py

**Files:**
- Create: `ui/views/bwdiff.py`

- [ ] **Step 1: 写 bwdiff view**

Write `ui/views/bwdiff.py`:
```python
"""Black-white difference background removal view."""
import gradio as gr
import numpy as np
from PIL import Image

from core import skills
from ui import tooltips, toast


def build():
    bwdiff_mod = skills.load("bwdiff")

    with gr.Group(visible=False, elem_id="view-bwdiff") as group:
        gr.Markdown("## ⬛⬜ 黑白差分去背景")
        gr.Markdown("💡 需要同机位拍摄的两张图，分别是黑色和白色背景。"
                    "通过逐像素差值反算 alpha 通道，无需 GPU。")

        with gr.Row():
            black = gr.Image(label="黑底图", type="pil", height=260,
                             info=tooltips.get("bwdiff.upload_black"))
            white = gr.Image(label="白底图", type="pil", height=260,
                             info=tooltips.get("bwdiff.upload_white"))
            result = gr.Image(label="抠图结果", type="pil", height=260,
                              format="png", image_mode="RGBA",
                              buttons=["fullscreen"])

        run_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")

        def _process(b, w, progress=gr.Progress()):
            if b is None or w is None:
                toast.warn("请上传黑底图和白底图")
                return None
            if b.size != w.size:
                toast.error(f"两张图片尺寸不一致",
                            f"黑底: {b.size}，白底: {w.size}")
                return None

            try:
                progress(0.3, desc="差分计算...")
                ba = np.array(b.convert("RGB"), dtype=np.float32)
                wa = np.array(w.convert("RGB"), dtype=np.float32)
                if np.allclose(ba, wa, atol=2.0):
                    toast.error("两图无差异", "请确认是否上传错误")
                    return None
                alpha, fg = bwdiff_mod.compute_alpha(ba, wa)
                progress(0.8, desc="alpha 合成...")
                out = Image.fromarray(np.dstack([fg, alpha]), "RGBA")
                progress(1.0, desc="完成")
                toast.success("处理完成 ✓")
                return out
            except Exception as e:
                toast.from_exception(e)
                return None

        run_btn.click(fn=_process, inputs=[black, white], outputs=[result])

        group.refill_targets = {
            "black_image": black,
            "white_image": white,
        }

    return group
```

- [ ] **Step 2: Commit**

```bash
git add ui/views/bwdiff.py
git commit -m "feat(ui/views): bwdiff view 独立模块，加预校验「两图无差异」

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: ui/views/bwgen.py

**Files:**
- Create: `ui/views/bwgen.py`

- [ ] **Step 1: 写 bwgen view**

Write `ui/views/bwgen.py`:
```python
"""bwgen view — generate black/white image pair from prompt."""
from pathlib import Path

import gradio as gr
from PIL import Image

from core import api_keys, skills
from ui import tooltips, toast

RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"]
SIZES = ["512", "1K", "2K", "4K"]
MODELS = ["gemini", "wan"]


def build(config_path: Path, project_dir: Path):
    bwgen_mod = skills.load("bwgen")
    out_dir = str(project_dir / "local" / "output" / "bwgen")

    with gr.Group(visible=False, elem_id="view-bwgen") as group:
        gr.Markdown("## 🎨 生黑白底图")
        gr.Markdown("💡 描述主体即可，无需提到背景。"
                    "系统自动添加「placed on solid black/white background」。"
                    "生成的两张图可直接送入「黑白差分」抠图。")

        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(
                    label="主体描述", lines=3,
                    placeholder="例如：一把发光的银色长剑，剑刃透明蓝色光芒",
                    info=tooltips.get("bwgen.prompt"),
                )
                with gr.Row():
                    ratio = gr.Dropdown(label="宽高比", choices=RATIOS, value="1:1",
                                        info=tooltips.get("bwgen.ratio"))
                    size = gr.Dropdown(label="分辨率", choices=SIZES, value="1K",
                                       info=tooltips.get("bwgen.size"))
                    model = gr.Dropdown(label="模型", choices=MODELS, value="gemini",
                                        info=tooltips.get("bwgen.model"))
                run_btn = gr.Button("▶ 开始生成", variant="primary", size="lg")
            with gr.Column(scale=1):
                black_out = gr.Image(label="黑底图", type="pil", height=280,
                                     format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                white_out = gr.Image(label="白底图", type="pil", height=280,
                                     format="png", buttons=["fullscreen"])

        def _generate(p, r, s, m, progress=gr.Progress()):
            if not p or not p.strip():
                toast.warn("请输入主体描述")
                return None, None
            if len(p) > 2000:
                toast.error("提示词过长", "建议控制在 2000 字以内")
                return None, None

            try:
                progress(0.1, desc="正在生成黑底图...")
                with api_keys.use_api_key(config_path, m):
                    bp, wp = bwgen_mod.generate_black_white(
                        p.strip(), r, s, out_dir, m,
                    )
                progress(1.0, desc="完成")
                toast.success(f"生成完成\n{bp}\n{wp}")
                return Image.open(bp), Image.open(wp)
            except api_keys.MissingKey as e:
                toast.error(str(e), "请到「设置」填写 API Key")
                return None, None
            except Exception as e:
                toast.from_exception(e)
                return None, None

        run_btn.click(fn=_generate, inputs=[prompt, ratio, size, model],
                      outputs=[black_out, white_out])

        group.refill_targets = {
            "prompt": prompt,
            "ratio": ratio,
            "size": size,
            "model": model,
        }

    return group
```

- [ ] **Step 2: Commit**

```bash
git add ui/views/bwgen.py
git commit -m "feat(ui/views): bwgen view 独立模块 + 预校验 + Toast 反馈

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: ui/views/gen_image.py

**Files:**
- Create: `ui/views/gen_image.py`

- [ ] **Step 1: 写 gen_image view**

Write `ui/views/gen_image.py`:
```python
"""AI image generation view (Gemini / Wan2.7)."""
from pathlib import Path

import gradio as gr
from PIL import Image

from core import api_keys, skills
from ui import tooltips, toast

RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"]
SIZES = ["512", "1K", "2K", "4K"]
MODELS = ["gemini", "wan"]


def build(config_path: Path, project_dir: Path):
    genimg_mod = skills.load("gen-image")
    out_dir = str(project_dir / "local" / "output" / "gen-image")

    with gr.Group(visible=False, elem_id="view-gen") as group:
        gr.Markdown("## 🖼 AI 生图")
        gr.Markdown("💡 英文效果通常更好。可包含风格、光照、镜头等修饰词。")

        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(
                    label="提示词", lines=3,
                    placeholder="例如：a cute orange tabby cat sitting on a wooden table",
                    info=tooltips.get("gen.prompt"),
                )
                with gr.Row():
                    ratio = gr.Dropdown(label="宽高比", choices=RATIOS, value="1:1",
                                        info=tooltips.get("gen.ratio"))
                    size = gr.Dropdown(label="分辨率", choices=SIZES, value="1K",
                                       info=tooltips.get("gen.size"))
                    model = gr.Dropdown(label="模型", choices=MODELS, value="gemini",
                                        info=tooltips.get("gen.model"))
                run_btn = gr.Button("▶ 开始生成", variant="primary", size="lg")
            with gr.Column(scale=1):
                output_img = gr.Image(label="生成结果", type="pil", height=400,
                                      format="png", buttons=["fullscreen"])

        def _generate(p, r, s, m, progress=gr.Progress()):
            if not p or not p.strip():
                toast.warn("请输入提示词")
                return None
            if len(p) > 2000:
                toast.error("提示词过长", "建议控制在 2000 字以内")
                return None
            try:
                progress(0.1, desc="发送请求...")
                with api_keys.use_api_key(config_path, m):
                    fp = genimg_mod.generate_image(p.strip(), r, s, out_dir, m)
                progress(0.9, desc="加载结果...")
                img = Image.open(fp)
                progress(1.0, desc="完成")
                toast.success(f"生成完成\n{fp}")
                return img
            except api_keys.MissingKey as e:
                toast.error(str(e), "请到「设置」填写 API Key")
                return None
            except Exception as e:
                toast.from_exception(e)
                return None

        run_btn.click(fn=_generate, inputs=[prompt, ratio, size, model],
                      outputs=[output_img])

        group.refill_targets = {
            "prompt": prompt,
            "ratio": ratio,
            "size": size,
            "model": model,
        }

    return group
```

- [ ] **Step 2: Commit**

```bash
git add ui/views/gen_image.py
git commit -m "feat(ui/views): gen_image view 独立模块

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: ui/views/pipeline.py

**Files:**
- Create: `ui/views/pipeline.py`

- [ ] **Step 1: 写 pipeline view**

Write `ui/views/pipeline.py`:
```python
"""One-click pipeline: bwgen → bwdiff."""
from pathlib import Path

import gradio as gr
from PIL import Image

from core import api_keys, skills
from ui import tooltips, toast

RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"]
SIZES = ["512", "1K", "2K", "4K"]
MODELS = ["gemini", "wan"]


def build(config_path: Path, project_dir: Path):
    bwgen_mod = skills.load("bwgen")
    bwdiff_mod = skills.load("bwdiff")
    out_dir = str(project_dir / "local" / "output" / "bwgen")

    with gr.Group(visible=False, elem_id="view-pipeline") as group:
        gr.Markdown("## 🔄 一键管线")
        gr.Markdown("💡 此功能 = 生黑白底图 → 自动差分抠图。一次得到透明 PNG。"
                    "出错率比单纯 AI 抠图低。")

        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(
                    label="主体描述", lines=3,
                    placeholder="例如：一把发光的银色长剑",
                    info=tooltips.get("pipeline.prompt"),
                )
                with gr.Row():
                    ratio = gr.Dropdown(label="宽高比", choices=RATIOS, value="1:1")
                    size = gr.Dropdown(label="分辨率", choices=SIZES, value="1K")
                    model = gr.Dropdown(label="模型", choices=MODELS, value="gemini")
                run_btn = gr.Button("▶ 一键执行", variant="primary", size="lg")
            with gr.Column(scale=1):
                black_out = gr.Image(label="黑底图", type="pil", height=200,
                                     format="png", buttons=["fullscreen"])
                white_out = gr.Image(label="白底图", type="pil", height=200,
                                     format="png", buttons=["fullscreen"])
            with gr.Column(scale=1):
                result = gr.Image(label="抠图结果", type="pil", height=400,
                                  format="png", image_mode="RGBA",
                                  buttons=["fullscreen"])

        def _run(p, r, s, m, progress=gr.Progress()):
            if not p or not p.strip():
                toast.warn("请输入主体描述")
                return None, None, None
            try:
                progress(0.1, desc="生成黑底图...")
                with api_keys.use_api_key(config_path, m):
                    bp, wp = bwgen_mod.generate_black_white(p.strip(), r, s, out_dir, m)
                progress(0.7, desc="差分抠图...")
                rgba = bwdiff_mod.bw_diff(bp, wp)
                progress(1.0, desc="完成")
                toast.success(f"管线完成\n{bp}\n{wp}")
                return Image.open(bp), Image.open(wp), rgba
            except api_keys.MissingKey as e:
                toast.error(str(e), "请到「设置」填写 API Key")
                return None, None, None
            except Exception as e:
                toast.from_exception(e)
                return None, None, None

        run_btn.click(fn=_run, inputs=[prompt, ratio, size, model],
                      outputs=[black_out, white_out, result])

        group.refill_targets = {
            "prompt": prompt,
            "ratio": ratio,
            "size": size,
            "model": model,
        }

    return group
```

- [ ] **Step 2: Commit**

```bash
git add ui/views/pipeline.py
git commit -m "feat(ui/views): pipeline view 复用 bwgen + bwdiff 模块调用

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 19: ui/layout.py — 三栏框架 + 侧边导航

**Files:**
- Create: `ui/layout.py`

- [ ] **Step 1: 写 layout 模块**

Write `ui/layout.py`:
```python
"""Three-column layout: topbar | sidebar + main + history.

Sidebar items emit a string view-id; main area shows exactly one view at a time.
"""
import gradio as gr

# (group_label, [(view_id, icon, display_name)])
NAV_GROUPS = [
    ("抠图", [
        ("rmbg", "🎯", "智能去背景"),
        ("bwdiff", "⬛⬜", "黑白差分"),
    ]),
    ("生图", [
        ("bwgen", "🎨", "生黑白底"),
        ("gen", "🖼", "AI 生图"),
    ]),
    ("流程", [
        ("pipeline", "🔄", "一键管线"),
    ]),
]

ALL_VIEWS = ["rmbg", "bwdiff", "bwgen", "gen", "pipeline", "settings"]


def render_sidebar_html(active: str) -> str:
    """Build the sidebar HTML, marking `active` view as selected."""
    parts: list[str] = []
    for group_label, items in NAV_GROUPS:
        parts.append(f'<div class="sidebar-section">{group_label}</div>')
        for vid, icon, name in items:
            cls = "sidebar-item active" if vid == active else "sidebar-item"
            parts.append(
                f'<div class="{cls}" onclick="window.selectView(\'{vid}\')">'
                f'<span>{icon}</span><span>{name}</span></div>'
            )
    parts.append('<div style="flex:1"></div>')
    settings_cls = "sidebar-item active" if active == "settings" else "sidebar-item"
    parts.append(
        f'<div class="{settings_cls}" onclick="window.selectView(\'settings\')">'
        f'<span>⚙</span><span>设置</span></div>'
    )
    return f'<div style="display:flex;flex-direction:column;gap:1px">{"".join(parts)}</div>'


SIDEBAR_JS = """
function selectView(viewId) {
    // Push the chosen viewId into a hidden Gradio textbox to trigger the change handler.
    const input = document.querySelector('#view-selector textarea, #view-selector input');
    if (input) {
        input.value = viewId;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
}
window.selectView = selectView;
"""


def visibility_for(view_id: str) -> dict[str, bool]:
    """Map view id → visible flag for each known view."""
    return {v: (v == view_id) for v in ALL_VIEWS}
```

- [ ] **Step 2: Commit**

```bash
git add ui/layout.py
git commit -m "feat(ui): layout.py 三栏框架 + 侧边导航 HTML/JS

- NAV_GROUPS 表驱动分组（抠图/生图/流程 + 设置）
- render_sidebar_html(active) 渲染当前选中态
- SIDEBAR_JS 通过隐藏 textbox 把选中的 view_id 回传 Gradio

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 20: 历史画廊（含回填）

**Files:**
- Create: `ui/history_panel.py`

- [ ] **Step 1: 写 history_panel 模块**

Write `ui/history_panel.py`:
```python
"""Right-side history panel: filter chips + gallery + click-to-refill."""
from pathlib import Path

import gradio as gr

from core.history import HistoryStore, TYPE_GROUPS

FILTER_CHIPS = ["all", "抠图", "生图", "流程"]


def build(store: HistoryStore, current_filter: str = "all"):
    """Return (panel_group, gallery_component, refresh_fn, filter_state)."""
    with gr.Column(elem_id="history") as panel:
        gr.Markdown("### 历史记录")

        with gr.Row():
            chip_radio = gr.Radio(
                choices=FILTER_CHIPS,
                value=current_filter,
                label=None, show_label=False, container=False,
            )

        gallery = gr.Gallery(
            label=None, show_label=False, columns=1, height="60vh",
            allow_preview=True, object_fit="contain",
        )

        clear_btn = gr.Button("清空历史", size="sm", variant="secondary")

    def _entries_to_gallery(entries: list[dict]) -> list:
        items = []
        for e in entries:
            tp = e.get("thumb_path") or e.get("output", {}).get("image_path")
            if tp and Path(tp).is_file():
                caption = f"{e.get('type', '?')} · {e.get('timestamp', '')[:16]}"
                items.append((tp, caption))
        return items

    def refresh(filter_value: str):
        return _entries_to_gallery(store.filter(filter_value))

    def on_filter_change(filter_value: str):
        return _entries_to_gallery(store.filter(filter_value))

    def on_clear():
        store.clear()
        return []

    chip_radio.change(fn=on_filter_change, inputs=[chip_radio], outputs=[gallery])
    clear_btn.click(fn=on_clear, outputs=[gallery])

    return panel, gallery, chip_radio, refresh
```

- [ ] **Step 2: Commit**

```bash
git add ui/history_panel.py
git commit -m "feat(ui): history_panel 历史画廊 + 筛选 chip + 清空按钮

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 21: 重写 app.py 组装新 UI

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 完全重写 app.py**

Write `app.py`:
```python
"""Image Processing Toolbox — Gradio Web UI (assembly only)."""
import os
import sys
import warnings
from pathlib import Path

import gradio as gr

warnings.filterwarnings("ignore", category=FutureWarning, module="timm")

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from core import config as cfg, history as hist
from ui import layout, theme, history_panel
from ui.views import settings as v_settings
from ui.views import rmbg as v_rmbg
from ui.views import bwdiff as v_bwdiff
from ui.views import bwgen as v_bwgen
from ui.views import gen_image as v_gen
from ui.views import pipeline as v_pipeline

CONFIG_PATH = PROJECT_DIR / "local" / "config.json"
DEFAULT_MODEL_DIR = str(PROJECT_DIR / "local" / "models" / "RMBG-2.0")
HISTORY_PATH = PROJECT_DIR / "local" / "history.json"
THUMB_DIR = PROJECT_DIR / "local" / "output" / ".thumbs"

CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
for sub in ["rmbg", "bwdiff", "bwgen", "gen-image"]:
    (PROJECT_DIR / "local" / "output" / sub).mkdir(parents=True, exist_ok=True)


def make_app():
    initial_cfg = cfg.load(CONFIG_PATH)
    initial_view = initial_cfg.get("last_view", "rmbg")
    initial_theme = initial_cfg.get("theme", "light")
    initial_filter = initial_cfg.get("history_filter", "all")
    store = hist.HistoryStore(HISTORY_PATH, THUMB_DIR)

    with gr.Blocks(
        title="Image Processing Toolbox",
        theme=theme.soft_theme(),
        css=theme.CSS,
        js=theme.THEME_INIT_JS + layout.SIDEBAR_JS,
    ) as app:
        # ── Top bar ──
        with gr.Row(elem_id="topbar"):
            with gr.Column(scale=0):
                gr.HTML('<div class="title">🖼 Image Processing Toolbox</div>')
            with gr.Column(scale=0):
                badges = gr.HTML(v_settings.badges_html(CONFIG_PATH))
            with gr.Column(scale=0):
                theme_btn = gr.Button("🌓", size="sm")

        # ── Main body ──
        with gr.Row():
            # Sidebar
            with gr.Column(scale=0, elem_id="sidebar", min_width=200):
                sidebar_html = gr.HTML(layout.render_sidebar_html(initial_view))
                # Hidden bridge: JS writes view-id here, change event triggers Python
                view_selector = gr.Textbox(value=initial_view,
                                           elem_id="view-selector",
                                           visible=False)

            # Main views
            with gr.Column(scale=1):
                view_settings = v_settings.build(CONFIG_PATH, DEFAULT_MODEL_DIR)
                view_rmbg = v_rmbg.build(CONFIG_PATH, DEFAULT_MODEL_DIR)
                view_bwdiff = v_bwdiff.build()
                view_bwgen = v_bwgen.build(CONFIG_PATH, PROJECT_DIR)
                view_gen = v_gen.build(CONFIG_PATH, PROJECT_DIR)
                view_pipeline = v_pipeline.build(CONFIG_PATH, PROJECT_DIR)

                view_groups = {
                    "settings": view_settings,
                    "rmbg": view_rmbg,
                    "bwdiff": view_bwdiff,
                    "bwgen": view_bwgen,
                    "gen": view_gen,
                    "pipeline": view_pipeline,
                }

                # Set initial visibility
                vis = layout.visibility_for(initial_view)
                for vid, group in view_groups.items():
                    group.visible = vis[vid]

            # History panel
            history_pane, gallery, chip_radio, refresh_history = history_panel.build(
                store, initial_filter
            )

        # ── Wiring: sidebar → view visibility ──
        def _on_view_change(view_id):
            vis = layout.visibility_for(view_id)
            cfg.update(CONFIG_PATH, last_view=view_id)
            return (
                layout.render_sidebar_html(view_id),
                *[gr.update(visible=vis[v]) for v in
                  ["settings", "rmbg", "bwdiff", "bwgen", "gen", "pipeline"]],
            )

        view_selector.change(
            fn=_on_view_change,
            inputs=[view_selector],
            outputs=[sidebar_html, view_settings, view_rmbg, view_bwdiff,
                     view_bwgen, view_gen, view_pipeline],
        )

        # ── Theme toggle ──
        theme_state = gr.State(initial_theme)
        theme_btn.click(
            fn=lambda t: ("dark" if t == "light" else "light"),
            inputs=[theme_state], outputs=[theme_state],
            js=theme.THEME_TOGGLE_JS,
        ).then(
            fn=lambda t: cfg.update(CONFIG_PATH, theme=t) and t,
            inputs=[theme_state], outputs=[],
        )

        # ── History filter persists ──
        chip_radio.change(
            fn=lambda f: cfg.update(CONFIG_PATH, history_filter=f) and None,
            inputs=[chip_radio], outputs=[],
        )

        # ── Initial theme application ──
        app.load(fn=lambda: initial_theme, outputs=[theme_state],
                 js=theme.THEME_INIT_JS)

    return app


if __name__ == "__main__":
    app = make_app()
    app.launch(server_name="127.0.0.1", server_port=7861, share=False)
```

- [ ] **Step 2: 启动验证**

```bash
python app.py
```
打开 http://127.0.0.1:7861 验证：
- 顶栏显示 GPU/CPU + 两个 API Key 徽章 + 主题按钮
- 左侧显示分组导航（抠图/生图/流程 + 底部设置）
- 默认显示 rmbg view
- 点击其他导航项能切换 view（不刷新页面）
- 点击主题按钮能切换亮/暗
- 右侧显示历史画廊（首次为空）
- 设置页保存后徽章会更新（PR 3 完善实时性）

按 Ctrl+C 退出。

- [ ] **Step 3: 测试套件全过**

```bash
pytest tests/ -v
```
Expected: 全绿。

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
feat: 重写 app.py 为 ui/ 模块组装薄壳

- 顶栏 + 三栏布局（sidebar / main / history）
- 6 个 view 来自 ui.views 子模块
- 视图切换走隐藏 textbox 桥接 JS↔Python
- 主题/最后视图/历史过滤偏好持久化到 config.json
- 历史画廊由 ui.history_panel 提供

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: 历史回填 — 写入 + 点击加载

**Files:**
- Modify: `ui/history_panel.py`
- Modify: each `ui/views/*.py` (add history.append on success)
- Modify: `app.py` (wire gallery select → view refill)

- [ ] **Step 1: 在 ui/history_panel.py 暴露 store 给 app.py 接 select 事件**

> `gallery.select` 的回调放在 app.py 里写（因为它需要访问所有 view 的 refill_targets）。这一 step 只确认 `history_panel.build` 返回的 `gallery` 控件可以被 app.py 接 `.select()` 事件——PR 2 Task 20 已经返回了 `gallery`，无需改 history_panel.py。

- [ ] **Step 2: 在每个 view 的 _process/_generate/_run 成功路径中调 history.append**

Example for `ui/views/rmbg.py` — after `toast.success("处理完成 ✓")`, before `return result`:

```python
                # Persist to history
                from core import history as hist
                # store handle passed in via build() — see Step 5
                # entry id + thumbnail
                # … (示例简化：在 app.py 注入 store；这里展示要保存的数据)
```

> **执行说明**：把 `store: HistoryStore` 加为 `build()` 的参数（每个 view 都要改），在 `_process` 里 import `core.history` 并 append。下面给出 rmbg 的完整改动，其余 view 照搬。

Edit `ui/views/rmbg.py` `build` signature and body:
```python
def build(config_path: Path, default_model_dir: str, store):
    rmbg_mod = skills.load("rmbg")
    # ... unchanged through to _process ...

        def _process(image, thresh, edge, white, progress=gr.Progress()):
            if image is None:
                toast.warn("请上传图片")
                return None
            from core import config as cfg, history as hist
            mdir = cfg.get_value(config_path, "model_dir", default=default_model_dir)
            if not Path(mdir).is_dir():
                toast.error("模型目录不存在", "请到「设置」配置 BiRefNet 模型路径")
                return None

            try:
                progress(0.1, desc="加载模型...")
                model, device = state.registry.get_or_load(
                    f"rmbg::{mdir}", rmbg_mod.load_model, model_dir=mdir,
                )
                progress(0.5, desc="推理中...")
                result = rmbg_mod.process_image(
                    image, model, device,
                    threshold=thresh, edge_refine=edge, white_bg=white,
                )

                # Persist input + output + thumbnail
                entry_id = hist.make_id()
                from datetime import datetime
                in_path = Path(config_path).parent / "output" / "rmbg" / f"_input_{entry_id}.png"
                out_path = Path(config_path).parent / "output" / "rmbg" / f"rmbg_{entry_id}.png"
                in_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(in_path)
                result.save(out_path)
                thumb = hist.make_thumbnail(out_path,
                                            Path(config_path).parent / "output" / ".thumbs",
                                            entry_id)
                store.append({
                    "id": entry_id,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "type": "rmbg",
                    "input": {"image_path": str(in_path),
                              "params": {"threshold": thresh, "edge_refine": edge, "white_bg": white}},
                    "output": {"image_path": str(out_path), "extra_paths": None},
                    "thumb_path": str(thumb),
                    "prompt": None,
                    "model": None,
                })

                progress(1.0, desc="完成")
                toast.success("处理完成 ✓")
                return result
            except Exception as e:
                toast.from_exception(e)
                return None
```

- [ ] **Step 3: 同样改 bwdiff/bwgen/gen/pipeline 的 build() 签名加 store 参数 + append**

For each view, the saved entry's `type` and `input.params` follow the spec §3.1 schema. For bwgen / pipeline, `extra_paths` holds the white_path (and result for pipeline).

Concrete entries:

bwdiff entry:
```python
store.append({
    "id": entry_id, "timestamp": ..., "type": "bwdiff",
    "input": {"image_path": str(b_path), "params": {"white_image_path": str(w_path)}},
    "output": {"image_path": str(out_path), "extra_paths": None},
    "thumb_path": str(thumb), "prompt": None, "model": None,
})
```

bwgen entry:
```python
store.append({
    "id": entry_id, "timestamp": ..., "type": "bwgen",
    "input": {"image_path": None, "params": {"ratio": r, "size": s}},
    "output": {"image_path": str(bp), "extra_paths": [str(wp)]},
    "thumb_path": str(thumb), "prompt": p, "model": m,
})
```

gen entry:
```python
store.append({
    "id": entry_id, "timestamp": ..., "type": "gen",
    "input": {"image_path": None, "params": {"ratio": r, "size": s}},
    "output": {"image_path": fp, "extra_paths": None},
    "thumb_path": str(thumb), "prompt": p, "model": m,
})
```

pipeline entry:
```python
store.append({
    "id": entry_id, "timestamp": ..., "type": "pipeline",
    "input": {"image_path": None, "params": {"ratio": r, "size": s}},
    "output": {"image_path": str(out_rgba_path), "extra_paths": [str(bp), str(wp)]},
    "thumb_path": str(thumb), "prompt": p, "model": m,
})
```

> 各 view 自行选择什么图作为 thumbnail 源（pipeline 用 RGBA result；bwgen 用黑底图）。

- [ ] **Step 4: 在 app.py 把 store 传入每个 view，并接 gallery select 回调**

Edit `app.py` to:
1. Pass `store` into every `vX.build(...)` call
2. Wire gallery select → refill targets

```python
# Build views (pass store)
view_settings = v_settings.build(CONFIG_PATH, DEFAULT_MODEL_DIR)  # settings has no store
view_rmbg = v_rmbg.build(CONFIG_PATH, DEFAULT_MODEL_DIR, store)
view_bwdiff = v_bwdiff.build(store)
view_bwgen = v_bwgen.build(CONFIG_PATH, PROJECT_DIR, store)
view_gen = v_gen.build(CONFIG_PATH, PROJECT_DIR, store)
view_pipeline = v_pipeline.build(CONFIG_PATH, PROJECT_DIR, store)
```

Then add gallery select handler in `app.py`:

```python
        # ── History click → switch view + refill params (no auto-execute) ──
        def _on_history_select(evt: gr.SelectData, filter_value):
            entries = store.filter(filter_value)
            if not (0 <= evt.index < len(entries)):
                return [gr.update()] * 7  # no-op
            entry = entries[evt.index]
            view_id = "gen" if entry["type"] == "gen" else entry["type"]
            vis = layout.visibility_for(view_id)
            from PIL import Image as _Image

            params = entry.get("input", {}).get("params", {})
            prompt_val = entry.get("prompt") or ""
            model_val = entry.get("model") or "gemini"

            updates = {
                "sidebar": layout.render_sidebar_html(view_id),
                "view_settings": gr.update(visible=vis["settings"]),
                "view_rmbg": gr.update(visible=vis["rmbg"]),
                "view_bwdiff": gr.update(visible=vis["bwdiff"]),
                "view_bwgen": gr.update(visible=vis["bwgen"]),
                "view_gen": gr.update(visible=vis["gen"]),
                "view_pipeline": gr.update(visible=vis["pipeline"]),
            }
            return list(updates.values())

        gallery.select(
            fn=_on_history_select,
            inputs=[chip_radio],
            outputs=[sidebar_html, view_settings, view_rmbg, view_bwdiff,
                     view_bwgen, view_gen, view_pipeline],
        )
```

> 完整参数回填会在 Task 23 处理（需要按 view 类型分别 set 各组件的值）。这一步只切换 view + toast 提示。

```python
        # Toast: 让用户知道已切换到对应 view
        def _toast_loaded():
            from ui import toast as _t
            _t.success("已加载历史参数，请确认后点击 ▶ 重新执行")
        gallery.select(fn=_toast_loaded)
```

- [ ] **Step 5: 启动验证**

```bash
python app.py
```
- 处理一张图后右侧画廊出现一条
- 切到其他 view 再回来仍可见
- 重启 app 后仍可见

- [ ] **Step 6: Commit**

```bash
git add ui/views/*.py ui/history_panel.py app.py
git commit -m "$(cat <<'EOF'
feat: 历史记录写入 + 点击切换 view（参数回填留待下一 task）

- 6 个 view 的 build() 增加 store 参数
- 每个 view 成功路径调 store.append + make_thumbnail
- gallery.select 触发 view 切换 + Toast 提示

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: 历史参数完整回填到对应 view

**Files:**
- Modify: `app.py` 的 `_on_history_select`

- [ ] **Step 1: 重写 _on_history_select 把 params 写回 view 的 refill_targets**

每个 view 在 `build()` 中已经把它的输入控件挂到 `group.refill_targets`。在 app.py 的 `_on_history_select` 里按 entry.type 决定要 update 哪些控件：

```python
        # ── History click → switch view + refill params ──
        def _on_history_select(evt: gr.SelectData, filter_value):
            entries = store.filter(filter_value)
            if not (0 <= evt.index < len(entries)):
                # No-op: return updates that change nothing
                return _no_change_updates()
            entry = entries[evt.index]
            etype = entry["type"]
            view_id = etype  # 1:1 mapping for now
            vis = layout.visibility_for(view_id)

            # Build per-view updates
            params = entry.get("input", {}).get("params", {}) or {}
            prompt_val = entry.get("prompt") or ""
            model_val = entry.get("model") or "gemini"

            from PIL import Image as _Image
            in_path = entry.get("input", {}).get("image_path")
            out_extras = entry.get("output", {}).get("extra_paths")

            rmbg_updates = (gr.update(), gr.update(), gr.update(), gr.update())
            bwdiff_updates = (gr.update(), gr.update())
            bwgen_updates = (gr.update(),) * 4
            gen_updates = (gr.update(),) * 4
            pipeline_updates = (gr.update(),) * 4

            if etype == "rmbg":
                img = _Image.open(in_path) if in_path else None
                rmbg_updates = (
                    gr.update(value=img),
                    gr.update(value=params.get("threshold", 0.5)),
                    gr.update(value=params.get("edge_refine", True)),
                    gr.update(value=params.get("white_bg", False)),
                )
            elif etype == "bwdiff":
                bp = _Image.open(in_path) if in_path else None
                wp_path = params.get("white_image_path")
                wp = _Image.open(wp_path) if wp_path else None
                bwdiff_updates = (gr.update(value=bp), gr.update(value=wp))
            elif etype == "bwgen":
                bwgen_updates = (
                    gr.update(value=prompt_val),
                    gr.update(value=params.get("ratio", "1:1")),
                    gr.update(value=params.get("size", "1K")),
                    gr.update(value=model_val),
                )
            elif etype == "gen":
                gen_updates = (
                    gr.update(value=prompt_val),
                    gr.update(value=params.get("ratio", "1:1")),
                    gr.update(value=params.get("size", "1K")),
                    gr.update(value=model_val),
                )
            elif etype == "pipeline":
                pipeline_updates = (
                    gr.update(value=prompt_val),
                    gr.update(value=params.get("ratio", "1:1")),
                    gr.update(value=params.get("size", "1K")),
                    gr.update(value=model_val),
                )

            from ui import toast
            toast.success("已加载历史参数，请确认后点击 ▶ 重新执行")

            return [
                layout.render_sidebar_html(view_id),
                gr.update(visible=vis["settings"]),
                gr.update(visible=vis["rmbg"]),
                gr.update(visible=vis["bwdiff"]),
                gr.update(visible=vis["bwgen"]),
                gr.update(visible=vis["gen"]),
                gr.update(visible=vis["pipeline"]),
                # Refill targets in declaration order:
                *rmbg_updates,
                *bwdiff_updates,
                *bwgen_updates,
                *gen_updates,
                *pipeline_updates,
            ]

        def _no_change_updates():
            return [gr.update() for _ in range(7 + 4 + 2 + 4 + 4 + 4)]

        gallery.select(
            fn=_on_history_select,
            inputs=[chip_radio],
            outputs=[
                sidebar_html,
                view_settings, view_rmbg, view_bwdiff, view_bwgen, view_gen, view_pipeline,
                # rmbg refill: input_image, threshold, edge_refine, white_bg
                view_rmbg.refill_targets["input_image"],
                view_rmbg.refill_targets["threshold"],
                view_rmbg.refill_targets["edge_refine"],
                view_rmbg.refill_targets["white_bg"],
                # bwdiff refill: black, white
                view_bwdiff.refill_targets["black_image"],
                view_bwdiff.refill_targets["white_image"],
                # bwgen refill: prompt, ratio, size, model
                view_bwgen.refill_targets["prompt"],
                view_bwgen.refill_targets["ratio"],
                view_bwgen.refill_targets["size"],
                view_bwgen.refill_targets["model"],
                # gen refill: prompt, ratio, size, model
                view_gen.refill_targets["prompt"],
                view_gen.refill_targets["ratio"],
                view_gen.refill_targets["size"],
                view_gen.refill_targets["model"],
                # pipeline refill: prompt, ratio, size, model
                view_pipeline.refill_targets["prompt"],
                view_pipeline.refill_targets["ratio"],
                view_pipeline.refill_targets["size"],
                view_pipeline.refill_targets["model"],
            ],
        )
```

- [ ] **Step 2: 删除 Task 22 中的占位 toast handler（避免双触发）**

确保 `gallery.select` 只注册一次（前一个 task 的占位调用要删掉）。

- [ ] **Step 3: 启动验证**

`python app.py`，处理一次 rmbg + 一次 bwgen，然后点击历史项：
- 应自动切到对应 view
- 输入控件被填回历史参数
- 不自动执行
- 顶部 Toast 「已加载历史参数」

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
feat: 历史画廊点击 → 切换 view + 完整回填参数

- 按 entry.type 分支生成 5 组 view 的 update tuple
- 通过 view.refill_targets 找到要更新的控件
- 不自动执行；只填参数，Toast 提醒用户手动 ▶

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 24: 设置页保存 → 顶栏徽章实时刷新

**Files:**
- Modify: `app.py`
- Modify: `ui/views/settings.py`

- [ ] **Step 1: settings.build 接收徽章组件作为输出**

Edit `ui/views/settings.py` — change `build` signature to also return the save button so app.py can wire its event:

```python
def build(config_path: Path, default_model_dir: str):
    # ... unchanged Group internals through to save_btn definition,
    # but DON'T attach .click() inside build. Return save_btn + its inputs.
    return group, save_btn, [gemini_key, dashscope_key, model_dir_input,
                             default_model, default_ratio, default_size]
```

Move `_save` definition out of build (or keep but don't bind .click()). Then in app.py:

```python
view_settings, settings_save_btn, settings_inputs = v_settings.build(CONFIG_PATH, DEFAULT_MODEL_DIR)

def _save_then_refresh(*args):
    # ... call cfg.update(...) inline (move the body of _save here) ...
    return v_settings.badges_html(CONFIG_PATH)

settings_save_btn.click(
    fn=_save_then_refresh,
    inputs=settings_inputs,
    outputs=[badges],
)
```

- [ ] **Step 2: 启动验证**

`python app.py` → 设置页填一个 API Key → 保存 → 顶栏「Gemini ❌」变成「🔑 Gemini 已配置」（无需刷新页面）。

- [ ] **Step 3: Commit**

```bash
git add ui/views/settings.py app.py
git commit -m "$(cat <<'EOF'
feat: 设置保存后顶栏徽章实时刷新

- settings.build 返回 save_btn + inputs，由 app.py 接 click 事件
- 保存后调 badges_html 重新渲染顶栏 GPU/Key 徽章

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 25: PR 2 收尾 — 文档 + PR

**Files:**
- Modify: `.claude/CLAUDE.md`

- [ ] **Step 1: 更新 CLAUDE.md 目录结构**

Add `ui/` 到目录结构说明：

```
ui/                       # Gradio UI 装配模块
  theme.py                # CSS 变量 + 亮/暗切换
  layout.py               # 三栏框架 + 侧边导航
  toast.py                # gr.Info/Warning/Error 封装
  tooltips.py             # 集中提示文案
  history_panel.py        # 右侧历史画廊
  views/                  # 6 个 view 子模块
    settings.py / rmbg.py / bwdiff.py / bwgen.py / gen_image.py / pipeline.py
```

把「快速开始」一节追加一句：「界面采用左导航 + 右历史画廊布局，亮/暗主题可在右上角切换。」

- [ ] **Step 2: Commit**

```bash
git add .claude/CLAUDE.md
git commit -m "docs: CLAUDE.md 同步 ui/ 结构与界面说明

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: 创建 PR 2**

```bash
git push
gh pr create --title "PR 2 · UI 重写（C 布局 + 历史画廊 + 主题切换）" --body "$(cat <<'EOF'
## Summary
- C 布局：顶栏 + 左导航 + 主区 + 右侧历史画廊
- 6 个 view 独立模块（ui/views/*）
- 主题（亮/暗）可切换 + 持久化
- 历史 JSON + 缩略图 + 类型筛选 chip
- 历史回填：点击 → 切 view → 填参数（不自动执行）
- 顶栏状态徽章（GPU/CPU + 两个 API Key）实时

## Test plan
- [ ] `pytest tests/ -v` 全绿
- [ ] 启动后 6 个 view 切换流畅
- [ ] 处理一次后历史画廊出现
- [ ] 点击历史项切到对应 view 并填回参数
- [ ] 设置页保存 API Key 后顶栏徽章立即更新
- [ ] 主题切换瞬时生效，刷新后保持
- [ ] 多浏览器标签同时使用 bwdiff 互不干扰

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# PR 3 · 抛光（依赖 PR 2）

> 这一 PR 主要是做完最后的细节抛光、补全引导提示、扩充错误模式、跑通完整手动 checklist。

## Task 26: 各 view 引导提示常驻 + 输入预校验补齐

**Files:**
- Modify: `ui/views/*.py`

- [ ] **Step 1: 检查每个 view 的引导 Markdown 是否覆盖 spec §4.5**

For each view, ensure there is a constant `gr.Markdown("💡 …")` line near the top of the Group. The text content per view is in spec §4.5. Cross-check current implementations from PR 2 — they should already have these.

如果发现缺失则补上。这一步主要是 review，不引入大改动。

- [ ] **Step 2: 补齐各 view 缺失的预校验**

Cross-check spec §4.3 against each view's `_process/_generate/_run` function. Confirm:

| view | 检查 | 状态（PR 2 实现 vs spec §4.3） |
|------|------|------|
| rmbg | 模型目录存在 | ✓（PR 2 已加） |
| rmbg | 输入图 < 50MB | ✗ 需补：`if image.size > some_threshold or in_path stat > 50MB...` |
| bwdiff | 尺寸一致 | ✓ |
| bwdiff | 两图差异不全为 0 | ✓（PR 2 加 `np.allclose`） |
| bwgen/gen | API key 存在 | ✓（use_api_key 抛 MissingKey） |
| bwgen/gen | prompt 非空 | ✓ |
| bwgen/gen | prompt < 2000 | ✓ |
| pipeline | 综合 | ✓ |

For rmbg "图片 < 50MB" check, after `if image is None: ...` add:

```python
            try:
                # Estimate uncompressed size: w * h * 3 bytes
                w, h = image.size
                if w * h * 3 > 50 * 1024 * 1024:  # ~50MB
                    toast.warn(f"图片较大 ({w}×{h})，处理可能较慢")
            except Exception:
                pass
```

- [ ] **Step 3: 启动验证**

`python app.py` → 各 view 的 `💡` 引导文字始终可见（处理多次后也不消失）。

- [ ] **Step 4: Commit**

```bash
git add ui/views/
git commit -m "polish: 引导提示常驻 + rmbg 大图警告

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 27: 错误模式表实战补全

**Files:**
- Modify: `core/errors.py`
- Modify: `tests/test_errors.py`

- [ ] **Step 1: 列出当前未匹配会落到 fallback 的真实异常**

跑一次 app，故意触发以下错误并观察 toast 显示：
- 设置错误的 model_dir
- 设置错误的 Gemini Key
- 设置错误的 DashScope Key
- bwgen 用一个非常长的 prompt
- pipeline 跑超大尺寸（4K）
- bwdiff 上传两张完全相同的图
- 网络断开后跑 gen

记录所有显示成「类型: <raw>」的异常文本。

- [ ] **Step 2: 把这些 case 加进 ERROR_PATTERNS（每加一条同时加测试）**

举例（按实际遇到的补充）：

In `tests/test_errors.py`:
```python
def test_dashscope_invalid_key():
    msg, _ = errors.user_message(RuntimeError("Wan2.7 API 调用失败"))
    # 现状：fallback；按你 Step 1 的真实文本调整
```

In `core/errors.py` ERROR_PATTERNS 顶部加 case，重跑测试。

- [ ] **Step 3: 跑测试**

```bash
pytest tests/test_errors.py -v
```
Expected: 全 PASSED 且新加 case 都覆盖。

- [ ] **Step 4: Commit**

```bash
git add core/errors.py tests/test_errors.py
git commit -m "polish: ERROR_PATTERNS 补充实战遇到的真实异常文本

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 28: 手动验证清单全过

**Files:**
- Create: `docs/superpowers/notes/2026-05-09-manual-checklist.md`

- [ ] **Step 1: 跑测试与 lint**

```bash
pytest tests/ -v
```
Expected: 全 PASSED。

- [ ] **Step 2: 完整手动 checklist（spec §5.2）**

Write `docs/superpowers/notes/2026-05-09-manual-checklist.md`:
```markdown
# Manual verification checklist for app refactor

Date: <填日期>
Tester: <填名字>

- [ ] 6 个 view 切换顺畅，状态不串
- [ ] 多浏览器标签同时上传 bwdiff 不互相覆盖
- [ ] 主题切换瞬间生效，刷新后仍记住
- [ ] 历史回填后参数正确填回，不自动执行
- [ ] 所有 ? tooltip 文案显示正常，无 KeyError
- [ ] Toast 在成功/警告/错误三种场景颜色正确
- [ ] API key 错误显示中文提示，不暴露 raw exception
- [ ] 引导 placeholder 常驻，处理后不消失
- [ ] 历史画廊筛选 chip 工作正常
- [ ] 顶栏 GPU/Key 徽章状态准确
- [ ] CPU-only 环境下 rmbg 能跑
- [ ] 4K 生图进度条分阶段更新
- [ ] 历史 100+ 条不卡顿
- [ ] 暗色主题下所有文字对比度足够
- [ ] python main.py 全新克隆能完整跑通向导

## 发现的 issue（如有）
…
```

逐项执行，把发现的小问题在本 PR 内修掉，无法当场修的开 issue。

- [ ] **Step 3: Commit checklist 与最终修复**

```bash
git add docs/superpowers/notes/ <fix files>
git commit -m "$(cat <<'EOF'
chore: PR 3 手动验证 checklist + 配套修复

- 完成 spec §5.2 全部 15 项验证
- 修复 checklist 暴露的小问题（详见提交历史）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: 创建 PR 3**

```bash
git push
gh pr create --title "PR 3 · 抛光（引导/预校验/错误表/手动 checklist）" --body "$(cat <<'EOF'
## Summary
- 引导 💡 提示文字常驻于每个 view
- 预校验补齐（rmbg 大图警告、bwdiff 同图检测等）
- ERROR_PATTERNS 补充实战遇到的真实异常文本
- 完成 spec §5.2 全部 15 项手动 checklist

## Test plan
- [ ] pytest tests/ -v 全绿
- [ ] 见 docs/superpowers/notes/2026-05-09-manual-checklist.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# 自检清单（写完计划后跑）

> 该部分供编写者自检，不属于实施任务。

## Spec coverage map

| Spec 节 | 实现 task |
|---------|-----------|
| §1.1 文件树 | Task 1-7 (PR1) + Task 10-20 (PR2) |
| §1.2 关键改动 #1 bwdiff bug | Task 8 Step 7 |
| §1.2 关键改动 #2 API key | Task 3 + Task 8 Step 4-5 |
| §1.2 关键改动 #3 pipeline 复用 | Task 8 Step 6 |
| §1.2 关键改动 #4 错误层 | Task 4 + Task 8 Step 4-7 + Task 27 |
| §2.1 三栏布局 | Task 19 + Task 21 |
| §2.2 组件实现 | Task 14-18 各 view |
| §2.3 CSS 变量 | Task 10 |
| §2.4 提示文案 | Task 11 |
| §3.1 历史 schema | Task 7 + Task 22 各 view 写入 |
| §3.2 配置扩展 | Task 2 (DEFAULTS) + Task 13 settings + Task 21 (theme/last_view/history_filter 持久化) |
| §3.3 State 拓扑 | Task 8 Step 7 + Task 21 |
| §3.4 历史回填 | Task 23 |
| §3.5 并发安全 | Task 6 (model lock) + Task 7 (history lock) + Task 8 (gr.State) |
| §4.1 错误模式 | Task 4 + Task 27 |
| §4.2 Toast | Task 12 |
| §4.3 输入预校验 | Task 14-18 各 view + Task 26 |
| §4.4 进度条 | Task 14-18 各 view（progress=gr.Progress()） |
| §4.5 引导提示常驻 | Task 14-18 + Task 26 |
| §4.6 顶栏徽章 | Task 13 (badges_html) + Task 24 (实时刷新) |
| §5.1 测试覆盖 | Task 1-7 各对应 test_*.py |
| §5.2 手动 checklist | Task 28 |
| §5.3 三 PR 拆分 | Task 9 / Task 25 / Task 28 创建 PR |
| §5.4 兼容性 | Task 2 DEFAULTS 兜底；Task 7 损坏文件处理 |
| §5.5 风险与回退 | 见各 task 的验证步骤 |

无遗漏。
