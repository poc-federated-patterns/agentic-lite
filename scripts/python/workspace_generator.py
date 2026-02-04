"""Generate VS Code workspace for a feature."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from .util import features_root, repos_root, read_yaml, repo_root

console = Console()


def generate_workspace(feature_key: str) -> Path:
    feature_dir = features_root() / feature_key
    if not feature_dir.exists():
        raise FileNotFoundError(f"Feature not found: {feature_key}")

    config = read_yaml(feature_dir / "config.yaml")
    repo_list = config.get("repos", [])
    repo_names = [r.split("/")[-1] for r in repo_list]

    folders = [
        {"name": "Assistant", "path": str(repo_root().absolute())},
    ]

    for repo_name in repo_names:
        repo_path = repos_root() / repo_name
        folders.append({"name": repo_name, "path": str(repo_path.absolute())})

    setup_cmd = f"bin/agentic workspace-setup {feature_key}"
    tasks = [
        {
            "label": "Agentic: Setup Repos",
            "type": "shell",
            "command": setup_cmd,
            "options": {"cwd": str(repo_root().absolute())},
            "problemMatcher": [],
            "presentation": {"reveal": "always", "panel": "new"},
            "runOptions": {"runOn": "folderOpen"},
        }
    ]

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


