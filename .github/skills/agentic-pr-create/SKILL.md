---
name: agentic-pr-create
description: Create main and supporting PRs using GitHub CLI.
---

Given:

- Main repo: `features/<FEATURE>/<TASK>/config.yaml` `main_repo`
- Supporting repos: `features/<FEATURE>/<TASK>/config.yaml` `repos`
- PR body: `features/<FEATURE>/<TASK>/pr/description.md`

Create:

- Main PR in `main_repo` with title `<TASK>: <title>` and the full PR body.
- Supporting PRs in other repos with body: `Supporting PR for <TASK>. Main PR: <URL>`.

Use `gh pr create` and ensure base branch is the repo default branch. Use the current branch as head.


