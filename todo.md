## Keep this file for tracking improvements

### Current Issue

- Validate the `GH_TOKEN` in `config/credentials.env` (debug logs show it is currently invalid in this environment).



### Recently Completed

- Cloning now uses shallow mode (`--depth 1`) for gh/ssh/https clone paths.
- Added auth diagnostics in `set-workspace-setup` (token source + gh auth status).
- Credentials from `config/credentials.env` now override existing env vars for CLI runs.
- Workspace terminals continue to source `credentials.env` and normalize `GH_TOKEN`/`GITHUB_TOKEN`.
- Updated on-attach message to use simplified `set-*` command flow.
- Improved clone recovery when `gh repo clone` times out and leaves partial folders.
- Added safer workspace setup behavior for non-git leftover directories.
- Added workspace-open instructions via a folder-open "next steps" task.
- Added tests for clone recovery and auth timeout handling.
- Ensured agentic-lite terminal startup activates `.venv` and shows next-step guidance inline.
- Added terminal icons (`hubot` for agentic-lite and `package` for repo terminals).
- Improved clone validation to only treat real git checkouts as existing (prevents empty repo false positives).


### Reminders

- Check staged changes and clean/simplify where appropriate
- Update docs/README when making changes
