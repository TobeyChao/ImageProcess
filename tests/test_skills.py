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
