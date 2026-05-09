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
