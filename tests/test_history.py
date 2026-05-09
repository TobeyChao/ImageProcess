"""Tests for core.history — JSON read/write, atomic, thread-safe, thumbnail."""
import json
import threading
from pathlib import Path

import pytest
from PIL import Image

from core import history


def _sample_entry(typ="rmbg") -> dict:
    return {
        "id": "20260509_120000_aaaa",
        "timestamp": "2026-05-09T12:00:00",
        "type": typ,
        "input": {"image_path": "x.png", "params": {"threshold": 0.5}},
        "output": {"image_path": "y.png", "extra_paths": None},
        "thumb_path": "z.webp",
        "prompt": None,
        "model": None,
    }


def test_load_returns_empty_when_missing(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    assert store.load() == []


def test_append_and_load(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    e = _sample_entry()
    store.append(e)
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0]["id"] == e["id"]


def test_filter_by_type(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    store.append(_sample_entry("rmbg"))
    e2 = _sample_entry("bwgen")
    e2["id"] = "different"
    store.append(e2)

    rmbg_only = store.filter("rmbg")
    assert len(rmbg_only) == 1
    assert rmbg_only[0]["type"] == "rmbg"

    abstract = store.filter("抠图")  # group: rmbg + bwdiff
    assert len(abstract) == 1
    assert abstract[0]["type"] == "rmbg"


def test_clear_removes_entries_and_thumbs(tmp_project):
    thumb_dir = tmp_project / "local" / "output" / ".thumbs"
    thumb_dir.mkdir(parents=True)
    (thumb_dir / "z.webp").write_bytes(b"fake")

    store = history.HistoryStore(tmp_project / "local" / "history.json", thumb_dir=thumb_dir)
    store.append(_sample_entry())

    store.clear()

    assert store.load() == []
    assert not (thumb_dir / "z.webp").exists()


def test_concurrent_appends(tmp_project):
    store = history.HistoryStore(tmp_project / "local" / "history.json",
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    barrier = threading.Barrier(5)

    def worker(i):
        barrier.wait()
        e = _sample_entry()
        e["id"] = f"id-{i}"
        store.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()

    loaded = store.load()
    assert len(loaded) == 5
    assert {e["id"] for e in loaded} == {f"id-{i}" for i in range(5)}


def test_make_thumbnail(tmp_project):
    img = Image.new("RGB", (512, 256), (255, 0, 0))
    src = tmp_project / "src.png"
    img.save(src)

    thumb_dir = tmp_project / "local" / "output" / ".thumbs"
    thumb_path = history.make_thumbnail(src, thumb_dir, "test_id")

    assert thumb_path.exists()
    assert thumb_path.suffix == ".webp"
    thumb = Image.open(thumb_path)
    assert max(thumb.size) <= 128


def test_corrupt_file_recovers_via_backup(tmp_project):
    history_path = tmp_project / "local" / "history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text("{not json", encoding="utf-8")

    store = history.HistoryStore(history_path,
                                 thumb_dir=tmp_project / "local" / "output" / ".thumbs")
    assert store.load() == []
    assert (tmp_project / "local" / "history.json.bak").exists()
