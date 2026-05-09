"""Shared pytest fixtures."""
import json
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
