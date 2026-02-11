#!/bin/bash
set -euo pipefail

# Show this message once per repository to avoid duplicate instructions
# when opening generated .code-workspace files.
MARKER_DIR=".agentic"
MARKER_FILE="${MARKER_DIR}/.on_attach_seen"
mkdir -p "${MARKER_DIR}"

if [[ -f "${MARKER_FILE}" && "${AGENTIC_FORCE_ATTACH_MSG:-0}" != "1" ]]; then
  exit 0
fi

cat <<'EOF'

Agentic-Lite quick guide:
  - README.md -> "Quick Start (1 minute)"
  - Init feature:    bin/agentic init <FEATURE-ID>
  - Set repos:       bin/agentic set-repos
  - Build workspace: bin/agentic set-workspace

Tip: if agentic commands fail, run:
  source .venv/bin/activate

EOF

touch "${MARKER_FILE}"


