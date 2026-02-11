## Keep this file for tracking improvements

### Current Issue

- The README seems wrong on core commands, as its mixing CLI with the Skills. The skills are for appending to the decision log, to creating the pr narrative in desired template (given the already built pr context)..... I don't think we need the agentic-pr-create skill as this is managed through the CLI? ... please analyse and clean up the README and optimize the skills / CLI accordingly.

### Recently Completed

- Debug logs moved behind debug mode (`--debug` or `AGENTIC_DEBUG=1`).
- Removed redundant global Codespaces attach message (kept workspace terminal guidance only).
- Repo terminals now run `gh auth setup-git` after loading credentials, to improve push auth behavior.


### Reminders

- Check staged changes and clean/simplify where appropriate
- Update docs/README when making changes
