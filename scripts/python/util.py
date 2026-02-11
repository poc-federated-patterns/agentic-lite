"""Shared utility helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

console = Console()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def features_root() -> Path:
    return repo_root() / "features"


def repos_root() -> Path:
    return repo_root().parent / "repos"


def load_env_file(env_path: Path, override_existing: bool = False) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        # Support inline comments: GH_TOKEN=xxx # comment
        if " #" in value and not (value.startswith('"') or value.startswith("'")):
            value = value.split(" #", 1)[0].rstrip()
        # Strip optional wrapping quotes
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if override_existing or key not in os.environ:
            os.environ[key] = value


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)


