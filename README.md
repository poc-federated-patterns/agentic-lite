# Agentic-Lite (Demo)

Lightweight workspace template to operationalize shared mental models for a team.
This repo provides a thin-slice workflow: fetch a feature from JIRA, choose repos,
generate a VS Code workspace, capture context, and prepare PRs.

## Quick Start (1 minute)

If you are in Codespaces, this should already be configured by the devcontainer.
If startup messages were missed, follow these steps:

```bash
# 1) Validate credentials
cp -n config/credentials.env.example config/credentials.env
# then edit config/credentials.env

# 2) Initialize feature + child tasks
bin/agentic init <FEATURE-ID> -c

# 3) Set repos for the feature
bin/agentic repos <FEATURE-ID>

# 4) Create and open workspace
bin/agentic workspace <FEATURE-ID>
code features/<FEATURE-ID>/<FEATURE-ID>.code-workspace
```

## Other Start

### 1) Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/python/requirements.txt

cp config/credentials.env.example config/credentials.env
# edit config/credentials.env with your JIRA credentials
```

### 2) Initialize a Feature

```bash
bin/agentic init FEAT-123 -c
```

Creates:

```
features/FEAT-123/
├── manifest.yaml
├── config.yaml
└── TASK-456/
    ├── manifest.yaml
    ├── config.yaml
    ├── diffs/
    ├── pr/
    └── research-notes/
```

### 3) Configure Repos

```bash
bin/agentic repos FEAT-123
```

### 4) Generate Workspace

```bash
bin/agentic workspace FEAT-123
code features/FEAT-123/FEAT-123.code-workspace
```

### 5) Capture Context + Build PR

```bash
# Generate diffs for all repos with a branch starting with TASK-456
bin/agentic diff TASK-456

# Or scope explicitly (backwards compatible)
bin/agentic diff FEAT-123 TASK-456 --repo org/service-a --repo org/service-b

# Task-only variants (feature inferred from local manifests)
bin/agentic log TASK-456
bin/agentic pr context TASK-456
bin/agentic pr build TASK-456
bin/agentic task-repos TASK-456
bin/agentic pr submit TASK-456
```

## Using Skills

This repo includes lightweight skills under `.github/skills/*` that Copilot can use to automate common tasks.

- Location: `.github/skills/<skill-name>/SKILL.md`
- What they do: Each skill describes a focused workflow (e.g., append a decision log, build a PR narrative, create PRs).

How to use with GitHub Copilot Chat in VS Code:

- Open Copilot Chat and ask to use a skill by name, providing the required inputs.
- Examples:
  - "Use the skill `agentic-decision-log` for TASK-456: Context=..., Decision=..., Alternatives=..., Consequences=..., Links=..."
  - "Run `agentic-pr-narrative` for FEAT-123/TASK-456 and update `pr/description.md`."
  - "Use `agentic-pr-create` for FEAT-123/TASK-456 to create main + supporting PRs."

Notes:
- Skills operate on workspace files; ensure feature/task folders exist from `bin/agentic init`.
- You can open the SKILL.md to see exact inputs and outputs each skill expects.

## Environment Variables

Set in `config/credentials.env`:

```
ATLASSIAN_BASE_URL=https://your-domain.atlassian.net
ATLASSIAN_EMAIL=you@example.com
ATLASSIAN_API_TOKEN=your_token
```

## Notes

- Repos are cloned into a sibling `../repos` folder (relative to this repo).
- Branching for code repos is manual. Branches should be prefixed with the task ID.
- The PR template is in `.github/PULL_REQUEST_TEMPLATE.md`.
- The generated workspace auto-opens one terminal for the assistant and one per repo; each loads credentials and activates `.venv` if present.


