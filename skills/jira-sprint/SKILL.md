---
name: jira-sprint
description: >-
  Active sprint, board, dates, and goal. Use for "what's the current
  sprint", "when does this sprint end", "what's the sprint goal".
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, sprint, board]
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
---

# Jira: Sprint

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py sprint [--board_id 42] [--project PAY]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

Resolves a board scoped to `--project` (or `JIRA_DEFAULT_PROJECT` if
omitted) so this reports the sprint for the project actually being
worked in, not an arbitrary board elsewhere in the instance -- pass
`--board_id` directly only if you already know the exact board. If
neither a project nor `--board_id` resolves, falls back to the first
board visible to the authenticated user instance-wide.

Prints one JSON document with the board and active sprint's dates/goal.
**Not every board has sprints** -- if the resolved board's `type` is
`"kanban"`, `"sprint"` is `null` and a `"note"` says so; use
`jira-kanban-status` for that board's column/status breakdown instead of
treating the missing sprint as an error or an empty backlog. Never
invent data not present in the JSON.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
