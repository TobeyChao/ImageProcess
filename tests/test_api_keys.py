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
