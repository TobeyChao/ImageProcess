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

# UI filter chips -> set of types
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
        """Filter entries by group name from TYPE_GROUPS, or by exact type name."""
        if group in TYPE_GROUPS:
            types = TYPE_GROUPS[group]
        else:
            # Treat as an exact type name (e.g. "rmbg", "bwdiff", "gen")
            types = {group}
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
                        # Relative paths are interpreted relative to thumb_dir
                        p = self.thumb_dir / p.name
                    if p.is_file():
                        try:
                            p.unlink()
                        except OSError:
                            pass
            self._write([])
