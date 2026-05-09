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
