"""Generate VS Code workspace for a feature."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

try:
    from .util import features_root, repos_root, read_yaml, repo_root
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from util import features_root, repos_root, read_yaml, repo_root

console = Console()


def generate_workspace(feature_key: str) -> Path:
    feature_dir = features_root() / feature_key
    if not feature_dir.exists():
        raise FileNotFoundError(f"Feature not found: {feature_key}")

    config = read_yaml(feature_dir / "config.yaml")
    repo_list = config.get("repos", [])
    repo_names = [r.split("/")[-1] for r in repo_list]
    credentials_path = repo_root() / "config" / "credentials.env"
    token_normalize = (
        'if [ -n "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then export GITHUB_TOKEN="$GH_TOKEN"; fi; '
        'if [ -n "${GITHUB_TOKEN:-}" ] && [ -z "${GH_TOKEN:-}" ]; then export GH_TOKEN="$GITHUB_TOKEN"; fi; '
    )
    git_auth_setup = (
        'if command -v gh >/dev/null 2>&1; then gh auth setup-git >/dev/null 2>&1 || true; fi; '
    )
    token_debug = (
        'if [ "${AGENTIC_DEBUG:-0}" = "1" ]; then '
        'gh_len=${#GH_TOKEN}; gh_tail=${GH_TOKEN: -6}; '
        'ght_len=${#GITHUB_TOKEN}; ght_tail=${GITHUB_TOKEN: -6}; '
        'echo "[agentic-lite] token debug: GH_TOKEN len=${gh_len} tail=*${gh_tail}, '
        'GITHUB_TOKEN len=${ght_len} tail=*${ght_tail}"; '
        "fi"
    )

    folders = [
        {"name": "agentic-lite", "path": str(repo_root().absolute())},
    ]

    for repo_name in repo_names:
        repo_path = repos_root() / repo_name
        folders.append({"name": repo_name, "path": str(repo_path.absolute())})

    setup_cmd = f"bin/agentic set-workspace-setup {feature_key}"
    tasks = [
        {
            "label": "agentic-lite: setup repos (manual)",
            "type": "shell",
            "command": setup_cmd,
            "options": {"cwd": str(repo_root().absolute())},
            "problemMatcher": [],
            "presentation": {"reveal": "always", "panel": "new"},
        }
    ]

    # Auto-open a terminal for agentic-lite root (load creds + activate venv)
    tasks.append(
        {
            "label": "Term: agentic-lite",
            "type": "shell",
            "command": "zsh",
            "args": [
                "-lc",
                (
                    "if [ -f config/credentials.env ]; then set -a; source config/credentials.env; set +a; fi; "
                    + token_normalize
                    + git_auth_setup
                    + token_debug
                    + "; "
                    + "if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi; "
                    + f'echo "agentic-lite workspace ready for {feature_key}"; '
                    + 'echo "Next:"; '
                    + 'echo "  1) Create task branches in repo terminals (prefix with TASK-ID)"; '
                    + 'echo "  2) Capture diffs: bin/agentic diff <TASK-ID>"; '
                    + 'echo "  3) Build PR: bin/agentic pr context <TASK-ID> && bin/agentic pr build <TASK-ID>"; '
                    + 'echo "  4) Configure repos: bin/agentic set-task-repos <TASK-ID>"; '
                    + 'echo "  5) Submit PRs: bin/agentic pr submit <TASK-ID>"; '
                    + "exec zsh -i"
                ),
            ],
            "options": {"cwd": str(repo_root().absolute())},
            "problemMatcher": [],
            "presentation": {"reveal": "silent", "panel": "dedicated"},
            "runOptions": {"runOn": "folderOpen"},
            "icon": {"id": "hubot"},
        }
    )

    # Auto-open a terminal per configured repo folder (if cloned)
    for repo_name in repo_names:
        repo_path = repos_root() / repo_name
        tasks.append(
            {
                "label": f"Term: {repo_name}",
                "type": "shell",
                "command": "zsh",
                "args": [
                    "-lc",
                    (
                        f'if [ -d "{repo_path}" ]; then cd "{repo_path}"; '
                        f'if [ -f "{credentials_path}" ]; then set -a; source "{credentials_path}"; set +a; fi; '
                        + token_normalize
                        + git_auth_setup
                        + token_debug
                        + "; "
                        + 'if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi; '
                        + "else "
                        + f'echo "Repo not cloned yet: {repo_name}. Run: bin/agentic set-workspace-setup {feature_key}"; '
                        + "fi; exec zsh -i"
                    ),
                ],
                "options": {"cwd": str(repo_root().absolute())},
                "problemMatcher": [],
                "presentation": {"reveal": "silent", "panel": "dedicated"},
                "runOptions": {"runOn": "folderOpen"},
                "icon": {"id": "package"},
            }
        )

    workspace = {
        "folders": folders,
        "settings": {
            "git.autofetch": True,
            "git.confirmSync": False,
            "git.enableSmartCommit": True,
            "githubPullRequests.pullRequestDescriptionGeneration": "copilot",
            "terminal.integrated.defaultProfile.osx": "zsh",
            "terminal.integrated.defaultProfile.linux": "bash",
        },
        "extensions": {
            "recommendations": [
                "github.copilot",
                "github.copilot-chat",
                "github.vscode-pull-request-github",
                "atlassian.atlascode",
                "redhat.vscode-yaml",
            ]
        },
        "tasks": {"version": "2.0.0", "tasks": tasks},
    }

    output_path = feature_dir / f"{feature_key}.code-workspace"
    with open(output_path, "w") as f:
        json.dump(workspace, f, indent=2)

    console.print(f"[green]Created workspace:[/green] {output_path}")
    console.print(f'To open: code "{output_path}"')
    return output_path


