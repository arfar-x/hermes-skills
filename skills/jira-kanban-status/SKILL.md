---
name: jira-kanban-status
description: >-
  Column breakdown and per-column issue counts for a kanban board. Use
  for "what's on the board", "how many tickets are in review", or any
  "current sprint" question that turns out to be about a kanban project
  (no sprints) instead.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, kanban, board]
    category: software-development
    requires_toolsets: [terminal]
required_environment_variables:
  - name: JIRA_BASE_URL
    prompt: "Jira base URL (e.g. https://jira.mycompany.com)"
    required_for: all functionality
  - name: JIRA_USERNAME
    prompt: "Jira username"
    required_for: basic auth mode (the default)
  - name: JIRA_PASSWORD
    prompt: "Jira password"
    required_for: basic auth mode (the default)
  - name: JIRA_DEFAULT_PROJECT
    prompt: "Default Jira project key (e.g. PAY), if you always work on the same project"
    required_for: optional -- if unset, you must resolve/pass --project yourself
---

# Jira: Kanban Status

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py kanban_status [--board_id 42] [--project PAY]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

Resolves a board scoped to `--project` (or `JIRA_DEFAULT_PROJECT` if
omitted) so this reports the board for the project actually being worked
in -- pass `--board_id` directly only if you already know the exact
board. Errors (as `"error"` in the JSON) if no board is found for the
resolved scope; don't fall back to an unrelated board.

If you don't know whether this project is Scrum or Kanban, use
`jira-board` instead -- it looks the type up from memory rather than
guessing, and still always fetches the live data (see below).

**Check memory for the board, not for the counts.** A project's board
type/id barely change; `issue_counts_by_column` does, constantly -- so
never skip *this* call because you remember a prior count, but if you
already know `--board_id` for this project (from memory, or a prior
`sprint`/`jira-board` call this conversation), pass it directly instead
of re-resolving via `--project` each time. Whatever this call teaches
you about the board itself (id, type, column names) is worth remembering
for next time (self-learning, same as `jira-project-context`'s
statuses/team/labels).

Prints one JSON document: `{"board_id": ..., "columns": [...],
"issue_counts_by_column": {...}}` -- `columns` is the board's real
column names (its actual workflow, not a guessed To Do/In Progress/Done
set), and `issue_counts_by_column` is how many issues currently sit in
each. Reason over this to answer "what's on the board" / "how loaded is
each stage" -- never invent a column name that isn't in the list.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
