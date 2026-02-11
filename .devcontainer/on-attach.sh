#!/bin/bash
set -euo pipefail

cat <<'EOF'

Agentic-Lite quick guide:
  - README.md -> "Quick Start (1 minute)"
  - Init feature:    bin/agentic init <FEATURE-ID>
  - Set repos:       bin/agentic set-repos
  - Build workspace: bin/agentic set-workspace

Tip: if agentic commands fail, run:
  source .venv/bin/activate

EOF


