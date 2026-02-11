"""Agentic-Lite CLI."""

from __future__ import annotations

import argparse
import base64
import os
import shutil
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


def _state_path() -> Path:
    return repo_root() / ".agentic" / "state.yaml"


def _save_active_feature(feature_key: str) -> None:
    path = _state_path()
    _ensure_dir(path.parent)
    write_yaml(path, {"active_feature": feature_key})


def _get_active_feature() -> str | None:
    state = read_yaml(_state_path())
    feature = state.get("active_feature")
    if feature and (_feature_dir(feature).exists()):
        return feature
    return None


def _latest_feature() -> str | None:
    base = features_root()
    if not base.exists():
        return None
    candidates = [p for p in base.iterdir() if p.is_dir()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name


def _resolve_feature_arg(feature: str | None) -> str:
    if feature:
        return feature
    current = _get_active_feature()
    if current:
        return current
    latest = _latest_feature()
    if latest:
        return latest
    raise RuntimeError(
        "No active feature found. Run `bin/agentic init <FEATURE-ID>` first "
        "or pass the feature key explicitly."
    )


def _load_credentials() -> None:
    # For workspace/auth flows we want credentials.env to be the source of truth.
    load_env_file(repo_root() / "config" / "credentials.env", override_existing=True)


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


def _resolve_feature_task(feature_or_task: str, maybe_task: str | None) -> tuple[str, str]:
    """Resolve inputs that can be either FEATURE TASK or TASK-only."""
    if maybe_task:
        return feature_or_task, maybe_task

    task_key = feature_or_task
    inferred = _find_feature_for_task(task_key)
    if not inferred:
        raise RuntimeError(
            f"Could not infer feature for task '{task_key}'. "
            "Use '<FEATURE> <TASK>' or initialize the task first."
        )
    return inferred, task_key


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _git(*args: str, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "never")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"git command timed out: {' '.join(exc.cmd)}") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _default_branch(cwd: Path) -> str:
    try:
        ref = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=cwd)
        # e.g. origin/main -> main
        return ref.split("/", 1)[1]
    except Exception:
        # Fallbacks
        for candidate in ("main", "master", "develop"):
            try:
                _git("rev-parse", f"origin/{candidate}", cwd=cwd)
                return candidate
            except Exception:
                continue
        return "main"


def _local_branches(cwd: Path) -> list[str]:
    try:
        out = _git(
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads",
            cwd=cwd,
        )
        return [b for b in out.splitlines() if b.strip()]
    except Exception:
        return []


def _head_branch(cwd: Path) -> str:
    try:
        return _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    except Exception:
        return ""


def _gh(*args: str, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env.setdefault("GH_PROMPT_DISABLED", "1")
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh command timed out: {' '.join(exc.cmd)}") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _normalize_github_token_env() -> None:
    # If GH_TOKEN is present from credentials.env, it takes precedence.
    if os.getenv("GH_TOKEN"):
        os.environ["GITHUB_TOKEN"] = os.environ["GH_TOKEN"]
    elif os.getenv("GITHUB_TOKEN"):
        os.environ["GH_TOKEN"] = os.environ["GITHUB_TOKEN"]


def _auth_debug_summary() -> str:
    env_source = "none"
    if (repo_root() / "config" / "credentials.env").exists():
        env_source = "credentials.env"
    gh_present = "yes" if os.getenv("GH_TOKEN") else "no"
    github_present = "yes" if os.getenv("GITHUB_TOKEN") else "no"
    token_hint = "GH_TOKEN" if os.getenv("GH_TOKEN") else ("GITHUB_TOKEN" if os.getenv("GITHUB_TOKEN") else "none")
    return (
        f"Auth debug: env_source={env_source}, GH_TOKEN={gh_present}, "
        f"GITHUB_TOKEN={github_present}, preferred_token={token_hint}"
    )


def _masked_token_hint(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        return f"{name}=<empty>"
    tail = value[-6:] if len(value) >= 6 else value
    has_space = any(c.isspace() for c in value)
    return f"{name}=len:{len(value)}, tail:*{tail}, has_space:{has_space}"


def _is_debug_mode(args: argparse.Namespace | None = None) -> bool:
    if args is not None and getattr(args, "debug", False):
        return True
    return os.getenv("AGENTIC_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _clone_repo(repo: str, repo_path: Path) -> str:
    """Clone repository using robust auth fallbacks.

    Order:
    1) gh repo clone (uses gh auth/session)
    2) git clone via SSH (git@github.com:org/repo.git)
    3) git clone via HTTPS with optional GH token header
    """
    _normalize_github_token_env()
    attempts: list[str] = []
    is_org_repo = "/" in repo and not repo.endswith(".git")

    def _has_git_dir(path: Path) -> bool:
        return path.exists() and (path / ".git").exists()

    def _is_valid_git_checkout(path: Path) -> bool:
        if not _has_git_dir(path):
            return False
        try:
            _git("rev-parse", "--is-inside-work-tree", cwd=path)
            _git("rev-parse", "HEAD", cwd=path)
            return True
        except Exception:
            return False

    def _cleanup_partial_dir(path: Path) -> None:
        if not path.exists():
            return
        if _is_valid_git_checkout(path):
            return
        shutil.rmtree(path, ignore_errors=True)

    def _recover_after_failure(path: Path) -> str | None:
        # gh clone can time out while the repo is actually cloned in background
        if _is_valid_git_checkout(path):
            return "existing"
        _cleanup_partial_dir(path)
        return None

    if _is_valid_git_checkout(repo_path):
        return "existing"

    if is_org_repo:
        gh_ready = False
        try:
            _gh("auth", "status", "-h", "github.com")
            gh_ready = True
        except Exception as exc:
            attempts.append(f"gh auth status failed: {exc}")

        if gh_ready:
            try:
                _gh("repo", "clone", repo, str(repo_path), "--", "--depth", "1")
                return "gh"
            except Exception as exc:
                attempts.append(f"gh repo clone failed: {exc}")
                recovered = _recover_after_failure(repo_path)
                if recovered:
                    return recovered

        ssh_url = f"git@github.com:{repo}.git"
        try:
            _git("clone", "--depth", "1", ssh_url, str(repo_path))
            return "ssh"
        except Exception as exc:
            attempts.append(f"ssh clone failed: {exc}")
            recovered = _recover_after_failure(repo_path)
            if recovered:
                return recovered

        https_url = f"https://github.com/{repo}.git"
        token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        try:
            if token:
                basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
                _git(
                    "-c",
                    f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}",
                    "clone",
                    "--depth",
                    "1",
                    https_url,
                    str(repo_path),
                )
            else:
                _git("clone", "--depth", "1", https_url, str(repo_path))
            return "https"
        except Exception as exc:
            attempts.append(f"https clone failed: {exc}")
            recovered = _recover_after_failure(repo_path)
            if recovered:
                return recovered
    else:
        try:
            _git("clone", "--depth", "1", repo, str(repo_path))
            return "git"
        except Exception as exc:
            attempts.append(f"git clone failed: {exc}")
            recovered = _recover_after_failure(repo_path)
            if recovered:
                return recovered

    raise RuntimeError(
        f"Failed to clone {repo}. "
        "Tried gh, ssh, and https methods. "
        "Run `gh auth status` and ensure token has repo access.\n"
        + "\n".join(attempts)
    )


def _configure_repo_auth(repo_path: Path) -> None:
    """Ensure git operations in this repo use the loaded GitHub token when available."""
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        return
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    try:
        # Disable credential helpers for this repo so token header is authoritative.
        _git("config", "--local", "credential.helper", "", cwd=repo_path)
    except Exception:
        pass
    try:
        _git(
            "config",
            "--local",
            "http.https://github.com/.extraheader",
            f"AUTHORIZATION: basic {basic}",
            cwd=repo_path,
        )
    except Exception:
        # Non-fatal: clone may still work via gh/ssh credentials.
        pass

    # Optional local identity setup for convenience.
    git_user_name = os.getenv("GIT_USER_NAME", "").strip()
    git_user_email = os.getenv("GIT_USER_EMAIL", "").strip()
    if git_user_name:
        try:
            _git("config", "--local", "user.name", git_user_name, cwd=repo_path)
        except Exception:
            pass
    if git_user_email:
        try:
            _git("config", "--local", "user.email", git_user_email, cwd=repo_path)
        except Exception:
            pass


def _prompt_list(prompt: str) -> list[str]:
    raw = input(prompt).strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def _prompt_select_one(options: list[str], prompt: str) -> str:
    if not options:
        return ""
    for i, item in enumerate(options, start=1):
        console.print(f"  {i}. {item}")
    raw = input(prompt).strip() or "1"
    try:
        idx = int(raw)
    except ValueError:
        idx = 1
    if idx < 1 or idx > len(options):
        idx = 1
    return options[idx - 1]


def _prompt_select_many(options: list[str], prompt: str) -> list[str]:
    if not options:
        return []
    raw = input(prompt).strip()
    if not raw:
        return []
    selected: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            idx = int(token)
        except ValueError:
            continue
        if 1 <= idx <= len(options):
            selected.append(options[idx - 1])
    return selected


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
    root_key = args.feature

    if not source.validate_key(root_key):
        raise ValueError(f"Invalid JIRA key: {root_key}")

    console.print(f"[bold]Fetching {root_key} from JIRA...[/bold]")
    root_item = source.fetch_item(root_key)
    if root_item.item_type != "feature":
        raise RuntimeError(
            f"{root_key} is '{root_item.item_type}'. "
            "Only feature-level stories are supported in agentic-lite. "
            "Please initialize using a feature key."
        )

    initialized_feature_keys: list[str] = [root_item.key]
    _init_feature(source, root_item, with_children=not args.no_children)
    _save_active_feature(root_item.key)

    branch_name = f"{root_key}-{_get_github_user()}"
    try:
        _git("checkout", "-b", branch_name, cwd=repo_root())
        console.print(f"[green]Created branch:[/green] {branch_name}")
    except Exception as exc:
        console.print(f"[yellow]Branch not created: {exc}[/yellow]")

    if initialized_feature_keys:
        console.print(f"[green]Initialized feature(s):[/green] {', '.join(initialized_feature_keys)}")
        console.print(f"[green]Active feature:[/green] {root_item.key}")
        console.print("Next: run `bin/agentic set-repos`")


def _init_feature(source: Any, feature: Any, with_children: bool) -> None:
    feature_key = feature.key
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

    if with_children:
        console.print(f"[bold]Fetching child tasks for {feature_key}...[/bold]")
        children = source.fetch_children(feature_key)
        task_keys = []
        for child in children:
            task_keys.append(child.key)
            _create_task(feature_key, child)
        feature_manifest["tasks"] = task_keys
        write_yaml(feature_dir / "manifest.yaml", feature_manifest)


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
    context_log = task_dir / "research-notes" / "gained-context.md"
    if not context_log.exists():
        context_log.write_text(f"# Gained Context for {task.key}\n\n")


def cmd_repos(args: argparse.Namespace) -> None:
    feature_key = _resolve_feature_arg(args.feature)
    feature_dir = _feature_dir(feature_key)
    config_path = feature_dir / "config.yaml"
    config = read_yaml(config_path)

    console.print(f"[bold]Configuring repos for feature:[/bold] {feature_key}")
    repos = _prompt_list("Enter repos (comma-separated, org/repo): ")
    if repos:
        config["repos"] = repos
        write_yaml(config_path, config)
        console.print("[green]Updated feature repos.[/green]")
        console.print("Next: run `bin/agentic set-workspace`")
    else:
        console.print("[yellow]No repos provided.[/yellow]")


def cmd_task_repos(args: argparse.Namespace) -> None:
    feature_key, task_key = _resolve_feature_task(args.feature_or_task, args.task)
    task_dir = _task_dir(feature_key, task_key)
    config_path = task_dir / "config.yaml"
    config = read_yaml(config_path)

    feature_repos = read_yaml(_feature_dir(feature_key) / "config.yaml").get("repos", [])
    if not feature_repos:
        console.print("[yellow]No feature repos configured; falling back to free text.[/yellow]")
        repos = _prompt_list("Repos for this task (comma-separated, org/repo): ")
        if repos:
            config["repos"] = repos
            main_repo = input("Main repo (org/repo): ").strip()
            if main_repo:
                config["main_repo"] = main_repo
        write_yaml(config_path, config)
        console.print("[green]Updated task repos.[/green]")
        return

    console.print("[bold]Select the main repo for this task:[/bold]")
    main_repo = _prompt_select_one(feature_repos, "Main repo number [1]: ")
    supporting_candidates = [r for r in feature_repos if r != main_repo]
    console.print("[bold]Select supporting repos (comma-separated numbers, empty for none):[/bold]")
    for i, item in enumerate(supporting_candidates, start=1):
        console.print(f"  {i}. {item}")
    supporting = _prompt_select_many(supporting_candidates, "Supporting repos: ")

    config["main_repo"] = main_repo
    config["repos"] = [main_repo, *[r for r in supporting if r != main_repo]]

    write_yaml(config_path, config)
    console.print("[green]Updated task repos.[/green]")


def cmd_workspace(args: argparse.Namespace) -> None:
    feature_key = _resolve_feature_arg(args.feature)
    _save_active_feature(feature_key)
    if not args.no_clone:
        console.print("[bold]Preparing repositories before workspace generation...[/bold]")
        cmd_workspace_setup(argparse.Namespace(feature=feature_key, debug=getattr(args, "debug", False)))
    output = generate_workspace(feature_key)
    console.print("Next steps:")
    console.print(f'  1) Open workspace: code "{output}"')
    console.print("  2) Start working in the opened terminals.")


def cmd_workspace_setup(args: argparse.Namespace) -> None:
    _load_credentials()
    _normalize_github_token_env()
    debug_mode = _is_debug_mode(args)
    if debug_mode:
        console.print(f"[dim]{_auth_debug_summary()}[/dim]")
        console.print(f"[dim]Auth debug: {_masked_token_hint('GH_TOKEN')}[/dim]")
        console.print(f"[dim]Auth debug: {_masked_token_hint('GITHUB_TOKEN')}[/dim]")
        try:
            _gh("auth", "status", "-h", "github.com")
            console.print("[dim]Auth debug: gh auth status is OK[/dim]")
        except Exception as exc:
            console.print(f"[dim]Auth debug: gh auth status failed ({exc})[/dim]")
    feature_key = _resolve_feature_arg(args.feature)
    feature_dir = _feature_dir(feature_key)
    config = read_yaml(feature_dir / "config.yaml")
    repos = config.get("repos", [])
    if not repos:
        console.print("[yellow]No repos configured. Run `bin/agentic repos` first.[/yellow]")
        return

    repos_root().mkdir(parents=True, exist_ok=True)
    failed: list[str] = []
    for repo in repos:
        repo_name = repo.split("/")[-1]
        repo_path = repos_root() / repo_name
        if repo_path.exists():
            if (repo_path / ".git").exists():
                try:
                    _git("rev-parse", "--is-inside-work-tree", cwd=repo_path)
                    _git("rev-parse", "HEAD", cwd=repo_path)
                except Exception:
                    console.print(f"[yellow]Found incomplete git checkout for {repo_name}, recreating...[/yellow]")
                    shutil.rmtree(repo_path, ignore_errors=True)
                    # continue to clone below
                else:
                    console.print(f"[dim]Repo exists: {repo_path}[/dim]")
                    _configure_repo_auth(repo_path)
                    continue
            else:
                # Recover from previously interrupted clone that left a non-git folder.
                console.print(f"[yellow]Found non-git folder for {repo_name}, recreating...[/yellow]")
                shutil.rmtree(repo_path, ignore_errors=True)
        if repo_path.exists():
            # Defensive cleanup for any leftovers.
            shutil.rmtree(repo_path, ignore_errors=True)
        console.print(f"[bold]Cloning {repo} for {feature_key}...[/bold]")
        try:
            method = _clone_repo(repo, repo_path)
            console.print(f"[green]Cloned {repo_name} via {method} into {repo_path}[/green]")
            _configure_repo_auth(repo_path)
        except Exception as exc:
            failed.append(f"{repo_name}: {exc}")
            console.print(f"[red]Failed cloning {repo_name}[/red]")

    if failed:
        console.print("\n[yellow]Some repositories failed to clone:[/yellow]")
        for msg in failed:
            console.print(f"  - {msg}")
        console.print("\nTry:")
        console.print("  1) gh auth status")
        console.print("  2) gh auth login -h github.com")
        console.print("  3) Verify token has org/repo access")
        return

    console.print("[green]Workspace repositories are ready.[/green]")


def cmd_log(args: argparse.Namespace) -> None:
    feature_key, task_key = _resolve_feature_task(args.feature_or_task, args.task)
    task_research = _task_dir(feature_key, task_key) / "research-notes"
    _ensure_dir(task_research)
    log_path = task_research / "gained-context.md"
    if not log_path.exists():
        log_path.write_text(f"# Gained Context for {task_key}\n\n")
    entry = input("Decision note: ").strip()
    if not entry:
        console.print("[yellow]No entry provided.[/yellow]")
        return
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    with open(log_path, "a") as f:
        f.write(f"- {timestamp} {entry}\n")
    console.print(f"[green]Logged context in:[/green] {log_path}")


def _resolve_repos_for_task(feature_key: str, task_key: str, repos: Iterable[str] | None) -> list[str]:
    if repos:
        return list(repos)
    task_config = read_yaml(_task_dir(feature_key, task_key) / "config.yaml")
    if task_config.get("repos"):
        return task_config["repos"]
    feature_config = read_yaml(_feature_dir(feature_key) / "config.yaml")
    return feature_config.get("repos", [])


def _detect_repos_for_task_by_branch_prefix(task_key: str) -> list[str]:
    names: list[str] = []
    root = repos_root()
    if not root.exists():
        return names
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if not (child / ".git").exists():
            continue
        branches = _local_branches(child)
        if any(b.startswith(task_key) for b in branches):
            names.append(child.name)
        else:
            head = _head_branch(child)
            if head.startswith(task_key):
                names.append(child.name)
    return sorted(names)


def _find_feature_for_task(task_key: str) -> str | None:
    base = features_root()
    if not base.exists():
        return None
    for feature_dir in base.iterdir():
        if not feature_dir.is_dir():
            continue
        if (feature_dir / task_key).exists():
            return feature_dir.name
    return None


def cmd_diff(args: argparse.Namespace) -> None:
    feature_key, task_key = _resolve_feature_task(args.feature_or_task, args.task)

    # Resolve repos from args/config; else auto-detect from local repos with matching branch prefix
    repos = []
    try:
        repos = _resolve_repos_for_task(feature_key, task_key, getattr(args, "repo", []))
    except Exception:
        repos = []

    task_dir = _task_dir(feature_key, task_key)
    diffs_dir = task_dir / "diffs"
    _ensure_dir(diffs_dir)

    repo_names: list[str]
    if repos:
        repo_names = [r.split("/")[-1] for r in repos]
    else:
        repo_names = _detect_repos_for_task_by_branch_prefix(task_key)
        if not repo_names:
            console.print("[yellow]No repos found with a matching branch prefix.[/yellow]")
            return

    for repo_name in repo_names:
        repo_path = repos_root() / repo_name
        if not repo_path.exists():
            console.print(f"[yellow]Repo not found: {repo_path}[/yellow]")
            continue

        base = _default_branch(repo_path)
        branches = _local_branches(repo_path)
        branch = next((b for b in branches if b.startswith(task_key)), None) or _head_branch(repo_path)

        if not branch or not (branch.startswith(task_key)):
            console.print(f"[dim]{repo_name}: no branch matching '{task_key}'[/dim]")
            continue

        # Prefer origin/base if available
        base_ref = f"origin/{base}"
        try:
            _git("rev-parse", base_ref, cwd=repo_path)
        except Exception:
            base_ref = base

        try:
            diff = _git("diff", f"{base_ref}...{branch}", cwd=repo_path)
        except Exception as exc:
            console.print(f"[yellow]{repo_name}: diff error: {exc}[/yellow]")
            continue

        output = diffs_dir / f"{repo_name}.patch"
        header = f"# Diff: {repo_name} ({base}...{branch})\n\n"
        content = header + (diff if diff.strip() else "# No differences found.\n")
        output.write_text(content)
        console.print(f"[green]Saved diff:[/green] {output}")


def cmd_pr_context(args: argparse.Namespace) -> None:
    feature_key, task_key = _resolve_feature_task(args.feature_or_task, args.task)
    output = build_context(feature_key, task_key)
    console.print(f"[green]Context created:[/green] {output}")


def cmd_pr_build(args: argparse.Namespace) -> None:
    feature_key, task_key = _resolve_feature_task(args.feature_or_task, args.task)
    feature_dir = _feature_dir(feature_key)
    task_dir = _task_dir(feature_key, task_key)
    template_path = repo_root() / ".github" / "PULL_REQUEST_TEMPLATE.md"
    description_path = task_dir / "pr" / "description.md"

    context_path = task_dir / "pr" / "context.md"
    if not context_path.exists():
        build_context(feature_key, task_key)

    template = template_path.read_text() if template_path.exists() else ""
    context_block = f"## Context\n\nSee `{context_path}`\n"
    if "<!-- AGENTIC_LITE_CONTEXT -->" in template:
        template = template.replace("<!-- AGENTIC_LITE_CONTEXT -->", context_block)
    else:
        template = template + "\n\n" + context_block

    description_path.write_text(template)
    console.print(f"[green]PR description created:[/green] {description_path}")


def cmd_pr_submit(args: argparse.Namespace) -> None:
    feature_key, task_key = _resolve_feature_task(args.feature_or_task, args.task)
    task_dir = _task_dir(feature_key, task_key)

    task_config_path = task_dir / "config.yaml"
    task_config = read_yaml(task_config_path)
    repos = task_config.get("repos", [])
    main_repo = task_config.get("main_repo", "")

    if not repos:
        repos = _resolve_repos_for_task(feature_key, task_key, None)
    if not repos:
        console.print("[yellow]No repos configured for this task.[/yellow]")
        console.print("Run: bin/agentic task-repos <TASK>")
        return

    if not main_repo:
        if len(repos) == 1:
            main_repo = repos[0]
        else:
            console.print("[bold]Select main repo for PR body:[/bold]")
            main_repo = _prompt_select_one(repos, "Main repo number [1]: ")
        task_config["main_repo"] = main_repo
        task_config["repos"] = repos
        write_yaml(task_config_path, task_config)

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
    base_branch = _default_branch(repo_path)
    head_branch = next((b for b in _local_branches(repo_path) if b.startswith(task_key)), "") or _head_branch(repo_path)
    if not head_branch or not head_branch.startswith(task_key):
        raise RuntimeError(f"{repo_name}: no local branch starting with {task_key}")

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
    )
    final_url = url.strip().splitlines()[-1]
    console.print(f"[green]Created PR:[/green] {final_url}")
    return final_url


def _create_supporting_pr(repo: str, title: str, main_url: str, task_key: str) -> None:
    repo_name = repo.split("/")[-1]
    repo_path = repos_root() / repo_name
    base_branch = _default_branch(repo_path)
    head_branch = next((b for b in _local_branches(repo_path) if b.startswith(task_key)), "") or _head_branch(repo_path)
    if not head_branch or not head_branch.startswith(task_key):
        console.print(f"[yellow]Skipping {repo_name}: no branch starting with {task_key}[/yellow]")
        return
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
    init_cmd.add_argument("-c", "--with-children", action="store_true", help=argparse.SUPPRESS)
    init_cmd.add_argument("-n", "--no-children", action="store_true")
    init_cmd.set_defaults(func=cmd_init)

    repos_cmd = sub.add_parser("repos", aliases=["set-repos"])
    repos_cmd.add_argument("feature", nargs="?")
    repos_cmd.set_defaults(func=cmd_repos)

    task_repos_cmd = sub.add_parser("task-repos", aliases=["set-task-repos"])
    task_repos_cmd.add_argument("feature_or_task")
    task_repos_cmd.add_argument("task", nargs="?")
    task_repos_cmd.set_defaults(func=cmd_task_repos)

    ws_cmd = sub.add_parser("workspace", aliases=["set-workspace"])
    ws_cmd.add_argument("feature", nargs="?")
    ws_cmd.add_argument("--no-clone", action="store_true")
    ws_cmd.add_argument("--debug", action="store_true")
    ws_cmd.set_defaults(func=cmd_workspace)

    ws_setup_cmd = sub.add_parser("workspace-setup", aliases=["set-workspace-setup"])
    ws_setup_cmd.add_argument("feature", nargs="?")
    ws_setup_cmd.add_argument("--debug", action="store_true")
    ws_setup_cmd.set_defaults(func=cmd_workspace_setup)

    log_cmd = sub.add_parser("log")
    log_cmd.add_argument("feature_or_task")
    log_cmd.add_argument("task", nargs="?")
    log_cmd.set_defaults(func=cmd_log)

    diff_cmd = sub.add_parser("diff")
    # Allow: diff FEATURE TASK  or diff TASK (feature optional)
    diff_cmd.add_argument("feature_or_task")
    diff_cmd.add_argument("task", nargs="?")
    diff_cmd.add_argument("--repo", action="append", default=[])
    diff_cmd.set_defaults(func=cmd_diff)

    pr_cmd = sub.add_parser("pr")
    pr_sub = pr_cmd.add_subparsers(dest="pr_cmd", required=True)

    pr_context = pr_sub.add_parser("context")
    pr_context.add_argument("feature_or_task")
    pr_context.add_argument("task", nargs="?")
    pr_context.set_defaults(func=cmd_pr_context)

    pr_build = pr_sub.add_parser("build")
    pr_build.add_argument("feature_or_task")
    pr_build.add_argument("task", nargs="?")
    pr_build.set_defaults(func=cmd_pr_build)

    pr_submit = pr_sub.add_parser("submit")
    pr_submit.add_argument("feature_or_task")
    pr_submit.add_argument("task", nargs="?")
    pr_submit.set_defaults(func=cmd_pr_submit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()


