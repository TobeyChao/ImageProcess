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
