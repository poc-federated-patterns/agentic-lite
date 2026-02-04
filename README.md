# Agentic-Lite (Demo)

Lightweight workspace template to operationalize shared mental models for a team.
This repo provides a thin-slice workflow: fetch a feature from JIRA, choose repos,
generate a VS Code workspace, capture context, and prepare PRs.

## Quick Start

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
bin/agentic diff FEAT-123 TASK-456 --repo org/service-a --repo org/service-b
bin/agentic pr context FEAT-123 TASK-456
bin/agentic pr build FEAT-123 TASK-456
bin/agentic task-repos FEAT-123 TASK-456
bin/agentic pr submit FEAT-123 TASK-456
```

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


