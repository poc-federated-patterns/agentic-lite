#!/bin/bash
set -euo pipefail

echo "==> Agentic-Lite devcontainer setup"

# Keep pre-commit tooling available and hooks installed.
uv tool install pre-commit --with pre-commit-uv || true
pre-commit install --install-hooks

# Local Python environment for agentic commands.
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r scripts/python/requirements.txt

# Ensure local credentials file exists for first run.
if [ -f "config/credentials.env.example" ] && [ ! -f "config/credentials.env" ]; then
  cp config/credentials.env.example config/credentials.env
  echo "==> Created config/credentials.env from example. Please fill your tokens."
fi

git config --global --add --bool push.autoSetupRemote true

if command -v devcontainer-info >/dev/null 2>&1; then
  devcontainer-info
fi

cat <<'EOF'

=========================================================
Agentic-Lite is ready.

Next steps:
  1) Fill credentials:
     - config/credentials.env
  2) Initialize feature from JIRA:
     - bin/agentic init <FEATURE-ID> -c
  3) Configure repos:
     - bin/agentic repos <FEATURE-ID>
  4) Generate/open workspace:
     - bin/agentic workspace <FEATURE-ID>
     - code features/<FEATURE-ID>/<FEATURE-ID>.code-workspace

If this message is missed, open README.md and follow "Quick Start (1 minute)".
=========================================================

EOF