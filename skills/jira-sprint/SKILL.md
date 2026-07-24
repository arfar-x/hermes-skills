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
  - name: JIRA_DEFAULT_PROJECT
    prompt: "Default Jira project key (e.g. PAY), if you always work on the same project"
    required_for: optional -- if unset, you must resolve/pass --project yourself
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

If you don't know whether this project is Scrum or Kanban, use
`jira-board` instead -- it looks the type up from memory rather than
guessing, and still always fetches the live data (see below).

**Check memory first.** A project's board type/id barely change; the
active sprint's content does. If you (or a prior call this conversation,
or your runtime's persistent memory) already know this project is
Kanban, skip this call entirely and go straight to `jira-kanban-status`
-- don't spend a call confirming something you already know. But don't
treat a *remembered sprint name/dates* as still current -- always call
this fresh for the sprint's actual content. If this call teaches you the
board type/id, that fact is worth remembering for next time (self-
learning, same as `jira-project-context`'s statuses/team/labels).

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
