---
name: jira-board
description: >-
  What's happening on my board right now -- the active sprint if this is
  a Scrum project, or the column/status breakdown if it's Kanban.
  Auto-detects which one applies, so you don't need to know in advance.
  Use for "what's going on with my board", "what's the current sprint",
  "how's the board looking" when you're not sure which type of project
  this is.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, sprint, board, kanban]
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

# Jira: Board

Read-only. This skill routes to whichever of `sprint`/`kanban_status` fits
-- run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py sprint [--project PAY] [--board_id 42]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

## Board type comes from memory, not a guess

A project's **board type** (Scrum, with sprints, vs. Kanban, without)
essentially never changes -- unlike the sprint/column data itself, which
you always need fresh, every call. This skill never re-derives the type
by speculatively calling one command to see what it says; it looks the
type up first:

1. **Type already known** (your runtime's persistent memory,
   `jira-project-context`, or an earlier call this conversation already
   told you): call the matching command directly and report its live
   result -- you're never skipping the actual data fetch, only the
   question of which command to run.
   ```bash
   # Scrum:
   python3 ../jira/scripts/jira_tool.py sprint [--project PAY] [--board_id 42]
   # Kanban:
   python3 ../jira/scripts/jira_tool.py kanban_status [--project PAY] [--board_id 42]
   ```
2. **Type not known yet for this project:** run `sprint` -- this is the
   first real request for this project's board, not a guess. Its result
   answers the question either way: an active sprint (Scrum), or a
   `"note"` saying the board is kanban (report via `kanban_status`
   instead, using the same `--project`/`--board_id`). The type it
   reveals is a side effect of a request you needed to make anyway, not
   an extra probe.
3. If `"board"` is null (no board found for the resolved scope), relay
   the `"note"` naming the project that was searched -- don't guess or
   invent a board.

**Remember the type once you know it.** Save it the same way
`jira-project-context` asks you to save a project's statuses/team/labels
-- this memory is self-learning. From then on, every future call (from
this skill, `jira-sprint`, or `jira-kanban-status`) goes straight to step
1 for this project; step 2 should only happen once per project, ever.

Already know which type of project this is? `jira-sprint`/
`jira-kanban-status` call the same underlying commands directly, without
this skill's type lookup.

Never invent data not present in either tool's JSON. If a result
contains `"error"`, tell the user what went wrong in plain language
instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
