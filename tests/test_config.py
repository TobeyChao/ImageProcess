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
