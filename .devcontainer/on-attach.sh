#!/bin/bash
set -euo pipefail

cat <<'EOF'

Agentic-Lite quick guide:
  - README.md -> "Quick Start (1 minute)"
  - Init feature:    bin/agentic init <FEATURE-ID> -c
  - Set repos:       bin/agentic repos <FEATURE-ID>
  - Build workspace: bin/agentic workspace <FEATURE-ID>

Tip: if agentic commands fail, run:
  source .venv/bin/activate

EOF


