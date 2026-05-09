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
