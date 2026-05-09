"""Lazy-loader for the skill scripts under .claude/skills/<name>/scripts/.

Each skill's primary script is loaded once and cached. Replaces the
ad-hoc importlib dance previously inlined in app.py.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent

# skill_name -> (relative script path under .claude/skills/<name>/scripts/, module name)
SKILL_SCRIPTS: dict[str, tuple[str, str]] = {
    "rmbg": ("rmbg/scripts/rmbg_process.py", "rmbg_process"),
    "bwdiff": ("bwdiff/scripts/bw_diff.py", "bw_diff"),
    "bwgen": ("bwgen/scripts/bw_gen.py", "bw_gen"),
    "gen-image": ("gen-image/scripts/gen_image.py", "gen_image"),
}

_cache: dict[str, ModuleType] = {}


def load(name: str) -> ModuleType:
    """Load and cache a skill script module. Raises KeyError for unknown name."""
    if name in _cache:
        return _cache[name]

    if name not in SKILL_SCRIPTS:
        raise KeyError(f"unknown skill: {name}")

    rel_path, mod_name = SKILL_SCRIPTS[name]
    full_path = REPO_ROOT / ".claude" / "skills" / rel_path

    spec = importlib.util.spec_from_file_location(mod_name, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load skill {name} at {full_path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _cache[name] = mod
    return mod
