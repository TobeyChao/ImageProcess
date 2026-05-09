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
    lock = threading.Lock()

    def slow_loader():
        with lock:
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
