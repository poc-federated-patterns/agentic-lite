## Keep this file for tracking improvements

### Current Issue

- No open issues captured.

- I like how the agentic-lite opens with the message and instructions for the TASK_ID and the icon! However, the Codespaces .devcontainer/on-attach.sh is still opening with the initial global message, that is redundant. This means we have two terminals for the agentic-line, and with two different messages. I only need one terminal and with the task-related messages (i.e. no need for the current on-attach ... or maybe we can do an if condition on that one?)

- I currently do not have the tokens activated in the workspace terminals of the repos... therefore I am not able to push changes. We need to activate the token from the credentials.env please


### Recently Completed

- Debug logs moved behind debug mode (`--debug` or `AGENTIC_DEBUG=1`).
- Removed redundant global Codespaces attach message (kept workspace terminal guidance only).
- Repo terminals now run `gh auth setup-git` after loading credentials, to improve push auth behavior.


### Reminders

- Check staged changes and clean/simplify where appropriate
- Update docs/README when making changes
