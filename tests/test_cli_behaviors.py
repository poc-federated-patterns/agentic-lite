import tempfile
from argparse import Namespace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import yaml

from scripts.python import cli


class TestCliBehaviors(TestCase):
    def test_resolve_feature_task_from_task_only(self):
        with patch.object(cli, "_find_feature_for_task", return_value="FEAT-1"):
            feature, task = cli._resolve_feature_task("TASK-1", None)
        self.assertEqual(feature, "FEAT-1")
        self.assertEqual(task, "TASK-1")

    def test_diff_task_only_autodetects_repo_by_branch_prefix(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            features = root / "features"
            repos = root / "repos"
            (features / "FEAT-1" / "TASK-1").mkdir(parents=True)
            (repos / "foo" / ".git").mkdir(parents=True)

            args = Namespace(feature_or_task="TASK-1", task=None, repo=[])
            with patch.object(cli, "features_root", return_value=features), patch.object(
                cli, "repos_root", return_value=repos
            ), patch.object(cli, "_find_feature_for_task", return_value="FEAT-1"), patch.object(
                cli, "_resolve_repos_for_task", return_value=[]
            ), patch.object(
                cli, "_detect_repos_for_task_by_branch_prefix", return_value=["foo"]
            ), patch.object(
                cli, "_local_branches", return_value=["TASK-1-impl"]
            ), patch.object(
                cli, "_head_branch", return_value="TASK-1-impl"
            ), patch.object(
                cli, "_default_branch", return_value="main"
            ), patch.object(
                cli, "_git", side_effect=["ok", "diff content"]
            ):
                cli.cmd_diff(args)

            patch_path = features / "FEAT-1" / "TASK-1" / "diffs" / "foo.patch"
            self.assertTrue(patch_path.exists())
            self.assertIn("diff content", patch_path.read_text())

    def test_pr_submit_uses_single_repo_as_main_when_not_set(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            features = root / "features"
            repos = root / "repos"
            task_dir = features / "FEAT-1" / "TASK-1"
            (task_dir / "pr").mkdir(parents=True)
            (task_dir / "pr" / "description.md").write_text("body")
            (task_dir / "config.yaml").write_text(yaml.safe_dump({"repos": ["org/foo"], "main_repo": ""}))
            (task_dir / "manifest.yaml").write_text(yaml.safe_dump({"task_key": "TASK-1", "title": "My task"}))
            (repos / "foo").mkdir(parents=True)

            args = Namespace(feature_or_task="TASK-1", task=None)
            with patch.object(cli, "features_root", return_value=features), patch.object(
                cli, "repos_root", return_value=repos
            ), patch.object(cli, "_find_feature_for_task", return_value="FEAT-1"), patch.object(
                cli, "_create_pr", return_value="https://example/pr/1"
            ) as create_pr, patch.object(cli, "_create_supporting_pr") as supporting:
                cli.cmd_pr_submit(args)

            create_pr.assert_called_once()
            supporting.assert_not_called()
            config = yaml.safe_load((task_dir / "config.yaml").read_text())
            self.assertEqual(config["main_repo"], "org/foo")

    def test_init_rejects_epic(self):
        root_item = type("Item", (), {"key": "EPIC-1", "item_type": "epic"})()
        source = type(
            "Source",
            (),
            {
                "validate_key": lambda _self, _k: True,
                "fetch_item": lambda _self, _k: root_item,
            },
        )()

        args = Namespace(feature="EPIC-1", no_children=False)
        with patch.object(cli, "_jira_source", return_value=source):
            with self.assertRaises(RuntimeError) as ctx:
                cli.cmd_init(args)
        self.assertIn("Only feature-level stories are supported", str(ctx.exception))

    def test_resolve_feature_arg_uses_active_feature(self):
        with patch.object(cli, "_get_active_feature", return_value="FEAT-22"):
            self.assertEqual(cli._resolve_feature_arg(None), "FEAT-22")


