"""Agentic-Lite CLI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from rich.console import Console

try:
    from .pr_context_builder import build_context
    from .util import (
        features_root,
        load_env_file,
        read_yaml,
        repo_root,
        repos_root,
        write_yaml,
    )
    from .workspace_generator import generate_workspace
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pr_context_builder import build_context
    from util import (
        features_root,
        load_env_file,
        read_yaml,
        repo_root,
        repos_root,
        write_yaml,
    )
    from workspace_generator import generate_workspace

console = Console()


def _load_credentials() -> None:
    load_env_file(repo_root() / "config" / "credentials.env")


def _jira_source():
    _load_credentials()
    try:
        from .sources.jira import JiraSource
    except ImportError:
        try:
            from sources.jira import JiraSource
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing Python dependencies. Run: pip install -r scripts/python/requirements.txt"
            ) from exc
    return JiraSource(
        base_url=os.getenv("ATLASSIAN_BASE_URL", ""),
        email=os.getenv("ATLASSIAN_EMAIL", ""),
        api_token=os.getenv("ATLASSIAN_API_TOKEN", ""),
    )


def _feature_dir(feature_key: str) -> Path:
    return features_root() / feature_key


def _task_dir(feature_key: str, task_key: str) -> Path:
    return _feature_dir(feature_key) / task_key


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _gh(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["gh", *args],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _prompt_list(prompt: str) -> list[str]:
    raw = input(prompt).strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def _get_github_user() -> str:
    try:
        return _gh("api", "user", "-q", ".login")
    except Exception:
        try:
            return _git("config", "user.name") or "user"
        except Exception:
            return "user"


def cmd_init(args: argparse.Namespace) -> None:
    source = _jira_source()
    feature_key = args.feature

    if not source.validate_key(feature_key):
        raise ValueError(f"Invalid JIRA key: {feature_key}")

    console.print(f"[bold]Fetching {feature_key} from JIRA...[/bold]")
    feature = source.fetch_item(feature_key)

    feature_dir = _feature_dir(feature_key)
    _ensure_dir(feature_dir)

    feature_manifest = {
        "feature_key": feature.key,
        "title": feature.title,
        "description": feature.description,
        "status": feature.status,
        "parent_key": feature.parent_key,
        "item_type": feature.item_type,
        "source": feature.source,
        "source_url": feature.source_url,
        "tasks": [],
    }
    write_yaml(feature_dir / "manifest.yaml", feature_manifest)

    if not (feature_dir / "config.yaml").exists():
        write_yaml(feature_dir / "config.yaml", {"repos": []})

    decisions_path = feature_dir / "decisions.md"
    if not decisions_path.exists():
        decisions_path.write_text(f"# Decisions for {feature_key}\n\n")

    if args.with_children:
        console.print("[bold]Fetching child tasks...[/bold]")
        children = source.fetch_children(feature_key)
        task_keys = []
        for child in children:
            task_keys.append(child.key)
            _create_task(feature_key, child)
        feature_manifest["tasks"] = task_keys
        write_yaml(feature_dir / "manifest.yaml", feature_manifest)

    branch_name = f"{feature_key}-{_get_github_user()}"
    try:
        _git("checkout", "-b", branch_name, cwd=repo_root())
        console.print(f"[green]Created branch:[/green] {branch_name}")
    except Exception as exc:
        console.print(f"[yellow]Branch not created: {exc}[/yellow]")

    console.print(f"[green]Initialized feature:[/green] {feature_key}")
    console.print(f"Next: run `bin/agentic repos {feature_key}`")


def _create_task(feature_key: str, task: Any) -> None:
    task_dir = _task_dir(feature_key, task.key)
    _ensure_dir(task_dir)
    write_yaml(
        task_dir / "manifest.yaml",
        {
            "task_key": task.key,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "acceptance_criteria": task.acceptance_criteria,
            "assignee": task.assignee,
            "labels": task.labels,
            "parent_key": task.parent_key,
            "item_type": task.item_type,
            "source": task.source,
            "source_url": task.source_url,
        },
    )
    if not (task_dir / "config.yaml").exists():
        write_yaml(task_dir / "config.yaml", {"repos": [], "main_repo": ""})
    for folder in ["diffs", "pr", "research-notes"]:
        _ensure_dir(task_dir / folder)


def cmd_repos(args: argparse.Namespace) -> None:
    feature_dir = _feature_dir(args.feature)
    config_path = feature_dir / "config.yaml"
    config = read_yaml(config_path)

    repos = _prompt_list("Enter repos (comma-separated, org/repo): ")
    if repos:
        config["repos"] = repos
        write_yaml(config_path, config)
        console.print("[green]Updated feature repos.[/green]")
    else:
        console.print("[yellow]No repos provided.[/yellow]")


def cmd_task_repos(args: argparse.Namespace) -> None:
    task_dir = _task_dir(args.feature, args.task)
    config_path = task_dir / "config.yaml"
    config = read_yaml(config_path)

    repos = _prompt_list("Repos for this task (comma-separated, org/repo): ")
    if repos:
        config["repos"] = repos

    main_repo = input("Main repo (org/repo): ").strip()
    if main_repo:
        config["main_repo"] = main_repo

    write_yaml(config_path, config)
    console.print("[green]Updated task repos.[/green]")


def cmd_workspace(args: argparse.Namespace) -> None:
    generate_workspace(args.feature)


def cmd_workspace_setup(args: argparse.Namespace) -> None:
    feature_dir = _feature_dir(args.feature)
    config = read_yaml(feature_dir / "config.yaml")
    repos = config.get("repos", [])
    if not repos:
        console.print("[yellow]No repos configured. Run `bin/agentic repos` first.[/yellow]")
        return

    repos_root().mkdir(parents=True, exist_ok=True)
    for repo in repos:
        repo_name = repo.split("/")[-1]
        repo_path = repos_root() / repo_name
        if repo_path.exists():
            console.print(f"[dim]Repo exists: {repo_path}[/dim]")
            continue
        url = f"https://github.com/{repo}.git"
        console.print(f"[bold]Cloning {repo}...[/bold]")
        _git("clone", url, str(repo_path))


def cmd_log(args: argparse.Namespace) -> None:
    feature_dir = _feature_dir(args.feature)
    log_path = feature_dir / "decisions.md"
    entry = input("Decision note: ").strip()
    if not entry:
        console.print("[yellow]No entry provided.[/yellow]")
        return
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    with open(log_path, "a") as f:
        f.write(f"- {timestamp} {entry}\n")
    console.print("[green]Logged decision.[/green]")


def _resolve_repos_for_task(feature_key: str, task_key: str, repos: Iterable[str] | None) -> list[str]:
    if repos:
        return list(repos)
    task_config = read_yaml(_task_dir(feature_key, task_key) / "config.yaml")
    if task_config.get("repos"):
        return task_config["repos"]
    feature_config = read_yaml(_feature_dir(feature_key) / "config.yaml")
    return feature_config.get("repos", [])


def cmd_diff(args: argparse.Namespace) -> None:
    repos = _resolve_repos_for_task(args.feature, args.task, args.repo)
    if not repos:
        console.print("[yellow]No repos configured for diff.[/yellow]")
        return

    task_dir = _task_dir(args.feature, args.task)
    diffs_dir = task_dir / "diffs"
    _ensure_dir(diffs_dir)

    for repo in repos:
        repo_name = repo.split("/")[-1]
        repo_path = repos_root() / repo_name
        if not repo_path.exists():
            console.print(f"[yellow]Repo not found: {repo_path}[/yellow]")
            continue
        diff = _git("diff", cwd=repo_path)
        output = diffs_dir / f"{repo_name}.patch"
        output.write_text(diff)
        console.print(f"[green]Saved diff:[/green] {output}")


def cmd_pr_context(args: argparse.Namespace) -> None:
    output = build_context(args.feature, args.task)
    console.print(f"[green]Context created:[/green] {output}")


def cmd_pr_build(args: argparse.Namespace) -> None:
    feature_dir = _feature_dir(args.feature)
    task_dir = _task_dir(args.feature, args.task)
    template_path = repo_root() / ".github" / "PULL_REQUEST_TEMPLATE.md"
    description_path = task_dir / "pr" / "description.md"

    context_path = task_dir / "pr" / "context.md"
    if not context_path.exists():
        build_context(args.feature, args.task)

    template = template_path.read_text() if template_path.exists() else ""
    context_block = f"## Context\n\nSee `{context_path}`\n"
    if "<!-- AGENTIC_LITE_CONTEXT -->" in template:
        template = template.replace("<!-- AGENTIC_LITE_CONTEXT -->", context_block)
    else:
        template = template + "\n\n" + context_block

    description_path.write_text(template)
    console.print(f"[green]PR description created:[/green] {description_path}")


def cmd_pr_submit(args: argparse.Namespace) -> None:
    feature_key = args.feature
    task_key = args.task
    task_dir = _task_dir(feature_key, task_key)

    task_config_path = task_dir / "config.yaml"
    task_config = read_yaml(task_config_path)
    repos = task_config.get("repos", [])
    main_repo = task_config.get("main_repo", "")

    if not repos or not main_repo:
        console.print("[yellow]Task repos or main_repo not set.[/yellow]")
        console.print(f"Run: bin/agentic task-repos {feature_key} {task_key}")
        return

    description_path = task_dir / "pr" / "description.md"
    if not description_path.exists():
        cmd_pr_build(args)

    task_manifest = read_yaml(task_dir / "manifest.yaml")
    title = f"{task_key}: {task_manifest.get('title', '')}"

    main_url = _create_pr(main_repo, title, description_path, task_key)
    for repo in repos:
        if repo == main_repo:
            continue
        _create_supporting_pr(repo, title, main_url, task_key)


def _create_pr(repo: str, title: str, body_path: Path, task_key: str) -> str:
    repo_name = repo.split("/")[-1]
    repo_path = repos_root() / repo_name
    base_branch = _gh("repo", "view", repo, "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name")
    head_branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_path)

    console.print(f"[bold]Creating PR for {repo}...[/bold]")
    url = _gh(
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        base_branch,
        "--head",
        head_branch,
        "--title",
        title,
        "--body-file",
        str(body_path),
        "--json",
        "url",
        "-q",
        ".url",
    )
    console.print(f"[green]Created PR:[/green] {url}")
    return url


def _create_supporting_pr(repo: str, title: str, main_url: str, task_key: str) -> None:
    repo_name = repo.split("/")[-1]
    repo_path = repos_root() / repo_name
    base_branch = _gh("repo", "view", repo, "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name")
    head_branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_path)
    body = f"Supporting PR for {task_key}. Main PR: {main_url}\n"

    console.print(f"[bold]Creating supporting PR for {repo}...[/bold]")
    _gh(
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        base_branch,
        "--head",
        head_branch,
        "--title",
        title,
        "--body",
        body,
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentic")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_cmd = sub.add_parser("init")
    init_cmd.add_argument("feature")
    init_cmd.add_argument("-c", "--with-children", action="store_true")
    init_cmd.set_defaults(func=cmd_init)

    repos_cmd = sub.add_parser("repos")
    repos_cmd.add_argument("feature")
    repos_cmd.set_defaults(func=cmd_repos)

    task_repos_cmd = sub.add_parser("task-repos")
    task_repos_cmd.add_argument("feature")
    task_repos_cmd.add_argument("task")
    task_repos_cmd.set_defaults(func=cmd_task_repos)

    ws_cmd = sub.add_parser("workspace")
    ws_cmd.add_argument("feature")
    ws_cmd.set_defaults(func=cmd_workspace)

    ws_setup_cmd = sub.add_parser("workspace-setup")
    ws_setup_cmd.add_argument("feature")
    ws_setup_cmd.set_defaults(func=cmd_workspace_setup)

    log_cmd = sub.add_parser("log")
    log_cmd.add_argument("feature")
    log_cmd.set_defaults(func=cmd_log)

    diff_cmd = sub.add_parser("diff")
    diff_cmd.add_argument("feature")
    diff_cmd.add_argument("task")
    diff_cmd.add_argument("--repo", action="append", default=[])
    diff_cmd.set_defaults(func=cmd_diff)

    pr_cmd = sub.add_parser("pr")
    pr_sub = pr_cmd.add_subparsers(dest="pr_cmd", required=True)

    pr_context = pr_sub.add_parser("context")
    pr_context.add_argument("feature")
    pr_context.add_argument("task")
    pr_context.set_defaults(func=cmd_pr_context)

    pr_build = pr_sub.add_parser("build")
    pr_build.add_argument("feature")
    pr_build.add_argument("task")
    pr_build.set_defaults(func=cmd_pr_build)

    pr_submit = pr_sub.add_parser("submit")
    pr_submit.add_argument("feature")
    pr_submit.add_argument("task")
    pr_submit.set_defaults(func=cmd_pr_submit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()


