---
name: agentic-decision-log
description: Append a structured decision log entry for a feature.
---

You are working in this repo. Append a decision log entry to the feature-level file:

- Target file: `features/<FEATURE>/decisions.md`

Use this template, filling in the user-provided details:

```
- YYYY-MM-DD HH:MM:SSZ
  - Context: <short context>
  - Decision: <decision made>
  - Alternatives: <brief alternatives>
  - Consequences: <impact>
  - Links: <PRs, tasks, docs>
```

If the file does not exist, create it with a title line `# Decisions for <FEATURE>` and then append the entry.


