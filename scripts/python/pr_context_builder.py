"""Build a structured PR context bundle."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from .util import features_root, read_yaml
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from util import features_root, read_yaml


def build_context(feature_key: str, task_key: str) -> Path:
    feature_dir = features_root() / feature_key
    task_dir = feature_dir / task_key

    feature_manifest = read_yaml(feature_dir / "manifest.yaml")
    task_manifest = read_yaml(task_dir / "manifest.yaml")

    decisions_path = feature_dir / "decisions.md"
    decisions_text = decisions_path.read_text() if decisions_path.exists() else ""

    research_dir = task_dir / "research-notes"
    research_notes = []
    if research_dir.exists():
        for note in sorted(research_dir.glob("*.md")):
            research_notes.append((note.name, note.read_text()))

    diffs_dir = task_dir / "diffs"
    diff_files = sorted(diffs_dir.glob("*.patch")) if diffs_dir.exists() else []

    output_path = task_dir / "pr" / "context.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# PR Context for {task_key}")
    lines.append("")
    lines.append("## Feature")
    lines.append(f"- Key: {feature_manifest.get('feature_key', feature_key)}")
    lines.append(f"- Title: {feature_manifest.get('title', '')}")
    lines.append("")
    lines.append("## Task")
    lines.append(f"- Key: {task_manifest.get('task_key', task_key)}")
    lines.append(f"- Title: {task_manifest.get('title', '')}")
    lines.append(f"- Status: {task_manifest.get('status', '')}")
    lines.append("")
    if task_manifest.get("acceptance_criteria"):
        lines.append("## Acceptance Criteria")
        lines.append(task_manifest.get("acceptance_criteria", ""))
        lines.append("")

    if decisions_text.strip():
        lines.append("## Decision Log")
        lines.append(decisions_text.strip())
        lines.append("")

    if research_notes:
        lines.append("## Research Notes")
        for name, text in research_notes:
            lines.append(f"### {name}")
            lines.append(text.strip())
            lines.append("")

    if diff_files:
        lines.append("## Diff Files")
        for diff in diff_files:
            lines.append(f"- {diff.name}")
        lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n")
    return output_path


