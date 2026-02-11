## Keep this file for tracking improvements

### Current Issue

Clean up README and stream-line it.

### Recently Completed

- Added skills usage guidance in `README.md`.
- `agentic diff` now supports task-only usage and auto-detects repos by task branch prefix.
- Workspace now opens assistant + repo terminals and loads credentials / activates `.venv` when present.
- `agentic pr context`, `agentic pr build`, `agentic pr submit`, `agentic task-repos`, and `agentic log` now support task-only usage (feature inferred).
- `task-repos` now offers menu-based selection from feature repos (main first, then supporting).
- Context notes moved to `research-notes/gained-context.md` and included in PR context bundle.
- `pr submit` now fails gracefully with clear guidance when task repo config is missing.
- Added lightweight tests for task inference, diff behavior, and PR submit prechecks.

### Reminders

- Check staged changes and clean/simplify where appropriate
- Update docs/README when making changes
