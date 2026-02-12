---
name: agentic-pr-narrative
description: Build a PR narrative from context and diffs.
---

Scope:
- This skill writes/updates `pr/description.md` only.
- PR creation and submission are handled by CLI (`bin/agentic pr submit`).

Read the following inputs:

- `features/<FEATURE>/<TASK>/pr/context.md`
- All files under `features/<FEATURE>/<TASK>/diffs/`
- `.github/PULL_REQUEST_TEMPLATE.md`

Write/update:

- `features/<FEATURE>/<TASK>/pr/description.md`

Requirements:

- Follow the PR template sections.
- Summarize key changes and risks.
- Include testing evidence or note if not run.
- Keep it concise and actionable for reviewers.


