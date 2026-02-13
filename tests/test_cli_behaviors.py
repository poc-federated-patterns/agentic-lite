import tempfile
from argparse import Namespace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import os
import subprocess

import yaml

from scripts.python import cli
from scripts.python.util import load_env_file


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

    def test_create_pr_when_already_exists_offers_update_and_returns_existing_url(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repos = root / "repos"
            (repos / "foo").mkdir(parents=True)

            # Simulate interactive environment + gh error containing PR URL
            gh_err = (
                'a pull request for branch "TASK-1-impl" into branch "main" already exists:\n'
                "https://github.com/org/foo/pull/123"
            )
            with patch.object(cli, "repos_root", return_value=repos), patch.object(
                cli, "_default_branch", return_value="main"
            ), patch.object(cli, "_local_branches", return_value=["TASK-1-impl"]), patch.object(
                cli, "_head_branch", return_value="TASK-1-impl"
            ), patch.object(cli, "_gh", side_effect=RuntimeError(gh_err)), patch.object(
                cli, "_is_interactive", return_value=True
            ), patch.object(cli, "_prompt_yes_no", return_value=True), patch.object(
                cli, "_update_pr_description"
            ) as upd:
                url = cli._create_pr("org/foo", "t", Path("/tmp/body.md"), "TASK-1")
            self.assertEqual(url, "https://github.com/org/foo/pull/123")
            self.assertTrue(upd.called)

    def test_pr_submit_runs_task_repos_when_not_set_and_interactive(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            features = root / "features"
            repos = root / "repos"
            task_dir = features / "FEAT-1" / "TASK-1"
            task_dir.mkdir(parents=True)
            (task_dir / "pr").mkdir(parents=True)
            (task_dir / "pr" / "description.md").write_text("body")
            (task_dir / "config.yaml").write_text(yaml.safe_dump({"repos": [], "main_repo": ""}))
            (task_dir / "manifest.yaml").write_text(yaml.safe_dump({"task_key": "TASK-1", "title": "My task"}))

            args = Namespace(feature_or_task="TASK-1", task=None)
            with patch.object(cli, "features_root", return_value=features), patch.object(
                cli, "repos_root", return_value=repos
            ), patch.object(cli, "_find_feature_for_task", return_value="FEAT-1"), patch.object(
                cli, "_is_interactive", return_value=True
            ), patch.object(cli, "cmd_task_repos") as task_repos, patch.object(
                cli, "_create_pr", return_value="https://example/pr/1"
            ) as create_pr:
                # Simulate task-repos updating config.yaml
                def _write_config(_ns):
                    (task_dir / "config.yaml").write_text(
                        yaml.safe_dump({"repos": ["org/foo"], "main_repo": "org/foo"})
                    )

                task_repos.side_effect = _write_config
                cli.cmd_pr_submit(args)

            self.assertTrue(task_repos.called)
            self.assertTrue(create_pr.called)

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

    def test_normalize_github_token_env_prefers_gh_token(self):
        old_gh = os.environ.get("GH_TOKEN")
        old_github = os.environ.get("GITHUB_TOKEN")
        try:
            os.environ["GH_TOKEN"] = "preferred"
            os.environ["GITHUB_TOKEN"] = "other"
            cli._normalize_github_token_env()
            self.assertEqual(os.environ.get("GITHUB_TOKEN"), "preferred")
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
            with patch.object(cli, "_gh", return_value="") as gh_call, patch.object(cli, "_git") as git_call:
                method = cli._clone_repo("org/foo", repo_path)
            self.assertEqual(method, "gh")
            git_call.assert_not_called()
            self.assertTrue(any(call.args[:4] == ("repo", "clone", "org/foo", str(repo_path)) for call in gh_call.call_args_list))

    def test_clone_repo_falls_back_to_ssh_when_gh_auth_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "foo"
            with patch.object(cli, "_gh", side_effect=RuntimeError("no gh auth")), patch.object(
                cli, "_git", return_value=""
            ) as git_call:
                method = cli._clone_repo("org/foo", repo_path)
            self.assertEqual(method, "ssh")
            self.assertTrue(git_call.called)
            self.assertIn("--depth", git_call.call_args.args)

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

    def test_load_credentials_overrides_existing_tokens(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = root / "config"
            config.mkdir(parents=True)
            (config / "credentials.env").write_text("GH_TOKEN=filetoken\nGITHUB_TOKEN=filetoken2\n")

            old_gh = os.environ.get("GH_TOKEN")
            old_github = os.environ.get("GITHUB_TOKEN")
            try:
                os.environ["GH_TOKEN"] = "oldtoken"
                os.environ["GITHUB_TOKEN"] = "oldtoken2"
                with patch.object(cli, "repo_root", return_value=root):
                    cli._load_credentials()
                self.assertEqual(os.environ.get("GH_TOKEN"), "filetoken")
                self.assertEqual(os.environ.get("GITHUB_TOKEN"), "filetoken2")
            finally:
                if old_gh is None:
                    os.environ.pop("GH_TOKEN", None)
                else:
                    os.environ["GH_TOKEN"] = old_gh
                if old_github is None:
                    os.environ.pop("GITHUB_TOKEN", None)
                else:
                    os.environ["GITHUB_TOKEN"] = old_github

    def test_load_env_file_parses_inline_comment_and_export(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / "credentials.env"
            env_file.write_text(
                "GH_TOKEN=ghp_1234567890 # inline comment\n"
                'export GITHUB_TOKEN="ghp_abcdefghij"\n'
            )
            old_gh = os.environ.get("GH_TOKEN")
            old_github = os.environ.get("GITHUB_TOKEN")
            try:
                os.environ.pop("GH_TOKEN", None)
                os.environ.pop("GITHUB_TOKEN", None)
                load_env_file(env_file, override_existing=True)
                self.assertEqual(os.environ.get("GH_TOKEN"), "ghp_1234567890")
                self.assertEqual(os.environ.get("GITHUB_TOKEN"), "ghp_abcdefghij")
            finally:
                if old_gh is None:
                    os.environ.pop("GH_TOKEN", None)
                else:
                    os.environ["GH_TOKEN"] = old_gh
                if old_github is None:
                    os.environ.pop("GITHUB_TOKEN", None)
                else:
                    os.environ["GITHUB_TOKEN"] = old_github

    def test_configure_repo_auth_sets_extraheader_and_identity(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            old_gh = os.environ.get("GH_TOKEN")
            old_name = os.environ.get("GIT_USER_NAME")
            old_email = os.environ.get("GIT_USER_EMAIL")
            try:
                os.environ["GH_TOKEN"] = "ghp_testtoken"
                os.environ["GIT_USER_NAME"] = "Test User"
                os.environ["GIT_USER_EMAIL"] = "test@example.com"
                with patch.object(cli, "_git", return_value="") as git_call:
                    cli._configure_repo_auth(repo)
                calls = [c.args for c in git_call.call_args_list]
                header_calls = [args for args in calls if "http.https://github.com/.extraheader" in args]
                self.assertTrue(len(header_calls) == 1)
                self.assertIn("AUTHORIZATION: basic ", header_calls[0][-1])
                self.assertTrue(any(("user.name" in args) for args in calls))
                self.assertTrue(any(("user.email" in args) for args in calls))
            finally:
                if old_gh is None:
                    os.environ.pop("GH_TOKEN", None)
                else:
                    os.environ["GH_TOKEN"] = old_gh
                if old_name is None:
                    os.environ.pop("GIT_USER_NAME", None)
                else:
                    os.environ["GIT_USER_NAME"] = old_name
                if old_email is None:
                    os.environ.pop("GIT_USER_EMAIL", None)
                else:
                    os.environ["GIT_USER_EMAIL"] = old_email


