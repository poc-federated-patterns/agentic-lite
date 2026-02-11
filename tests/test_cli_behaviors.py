import tempfile
from argparse import Namespace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import os
import subprocess

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

    def test_workspace_runs_setup_by_default(self):
        args = Namespace(feature="FEAT-1", no_clone=False)
        with patch.object(cli, "_save_active_feature"), patch.object(
            cli, "cmd_workspace_setup"
        ) as setup_call, patch.object(cli, "generate_workspace", return_value=Path("/tmp/w.code-workspace")):
            cli.cmd_workspace(args)
        setup_call.assert_called_once()

    def test_workspace_setup_recreates_non_git_folder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            features = root / "features"
            repos = root / "repos"
            feature_dir = features / "FEAT-1"
            feature_dir.mkdir(parents=True)
            (feature_dir / "config.yaml").write_text(yaml.safe_dump({"repos": ["org/foo"]}))
            broken_repo = repos / "foo"
            broken_repo.mkdir(parents=True)
            (broken_repo / "file.txt").write_text("partial")

            args = Namespace(feature=None)
            with patch.object(cli, "features_root", return_value=features), patch.object(
                cli, "repos_root", return_value=repos
            ), patch.object(cli, "_resolve_feature_arg", return_value="FEAT-1"), patch.object(
                cli, "_clone_repo", return_value="gh"
            ) as clone_call:
                cli.cmd_workspace_setup(args)
            clone_call.assert_called_once()

    def test_normalize_github_token_env(self):
        old_gh = os.environ.get("GH_TOKEN")
        old_github = os.environ.get("GITHUB_TOKEN")
        try:
            os.environ.pop("GH_TOKEN", None)
            os.environ["GITHUB_TOKEN"] = "abc"
            cli._normalize_github_token_env()
            self.assertEqual(os.environ.get("GH_TOKEN"), "abc")
        finally:
            if old_gh is None:
                os.environ.pop("GH_TOKEN", None)
            else:
                os.environ["GH_TOKEN"] = old_gh
            if old_github is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = old_github

    def test_clone_repo_prefers_gh_for_org_repo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "foo"
            with patch.object(cli, "_gh", return_value=""), patch.object(cli, "_git") as git_call:
                method = cli._clone_repo("org/foo", repo_path)
            self.assertEqual(method, "gh")
            git_call.assert_not_called()

    def test_clone_repo_falls_back_to_ssh_when_gh_auth_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "foo"
            with patch.object(cli, "_gh", side_effect=RuntimeError("no gh auth")), patch.object(
                cli, "_git", return_value=""
            ) as git_call:
                method = cli._clone_repo("org/foo", repo_path)
            self.assertEqual(method, "ssh")
            self.assertTrue(git_call.called)

    def test_git_timeout_is_raised_as_runtime_error(self):
        with patch("scripts.python.cli.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["git", "clone"], timeout=1)):
            with self.assertRaises(RuntimeError) as ctx:
                cli._git("clone", "x")
        self.assertIn("timed out", str(ctx.exception))

    def test_clone_repo_returns_existing_when_git_dir_present_after_gh_timeout(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "foo"
            (repo_path / ".git").mkdir(parents=True)
            with patch.object(cli, "_gh", side_effect=RuntimeError("gh timeout")) as gh_call, patch.object(
                cli, "_git", return_value="ok"
            ) as git_call:
                method = cli._clone_repo("org/foo", repo_path)
            self.assertEqual(method, "existing")
            gh_call.assert_not_called()
            self.assertGreaterEqual(git_call.call_count, 2)


