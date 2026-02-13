import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import yaml

from scripts.python import pr_context_builder


class TestPrContextBuilder(TestCase):
    def test_build_context_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            feature_dir = tmp_path / "features" / "FEAT-1"
            task_dir = feature_dir / "TASK-1"
            task_dir.mkdir(parents=True)

            (feature_dir / "manifest.yaml").write_text(
                yaml.safe_dump({"feature_key": "FEAT-1", "title": "Feature"})
            )
            (task_dir / "manifest.yaml").write_text(
                yaml.safe_dump({"task_key": "TASK-1", "title": "Task", "status": "Todo"})
            )
            (task_dir / "research-notes").mkdir()
            (task_dir / "research-notes" / "gained-context.md").write_text("Decision entry\n")
            (task_dir / "research-notes" / "note.md").write_text("Research\n")
            (task_dir / "diffs").mkdir()
            (task_dir / "diffs" / "repo.patch").write_text("diff\n")

            with patch.object(pr_context_builder, "features_root", return_value=tmp_path / "features"):
                output = pr_context_builder.build_context("FEAT-1", "TASK-1")

            self.assertTrue(output.exists())
            content = output.read_text()
            self.assertIn("PR Context for TASK-1", content)
            self.assertIn("Ticket Manifest (raw)", content)
            self.assertIn("Acceptance criteria must be extracted", content)
            self.assertIn("Decision entry", content)
            self.assertIn("repo.patch", content)


