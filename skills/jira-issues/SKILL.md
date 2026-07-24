---
name: jira-issues
description: >-
  Runs an arbitrary JQL search against Jira and returns structured issue
  results. Use for "find issues where...", "which of my tickets haven't
  been updated recently", or any query not covered by a more specific
  Jira skill.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, search]
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

# Jira: Issue Search

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py search --jql "assignee = currentUser() AND updated <= -14d" \
  [--max_results 100] [--only summary,status,priority] [--fields customfield_10056]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--jql` is required. Prints one JSON document: structured issue results
matching the query. `key`, `url`, `custom_fields`, and `blocked` are
always present; every other field is controlled by `--only`. Never
invent or fabricate issue data -- everything you state must come from
this JSON.

- `--only` (optional, comma-separated named fields, e.g.
  `summary,status,priority,labels,description`) asks for exactly the
  fields you need instead of everything -- the main lever for keeping
  bulk results token-cheap. Omit it for the default set: everything
  except `description` and the time-tracking fields (`description` is
  free text that can run long, and is rarely needed to scan many issues
  at once -- pass it explicitly, e.g. `--only summary,description`, when
  you actually need it). Valid names: `summary`, `status`, `priority`,
  `issue_type`, `assignee`, `reporter`, `updated`, `created`, `due_date`,
  `labels`, `links`, `description`, `components`, `subtasks`,
  `original_estimate_seconds`, `time_spent_seconds`,
  `remaining_estimate_seconds`.
- `--fields` (optional, comma-separated) requests extra *raw* Jira field
  IDs in addition to `--only` -- use it for instance-specific custom
  fields, e.g. a "Figma Link" field, always surfaced in `custom_fields`.
  Discover its ID first by running `list_fields` (via the `jira` skill's
  CLI, `python3 ../jira/scripts/jira_tool.py list_fields`); never guess a
  `customfield_NNNNN` id.
- **`--only`'s field names and `--jql`'s field names are different
  vocabularies -- don't mix them up.** `--only` uses this skill's own
  snake_case names (`due_date`, `issue_type`); `--jql` uses Jira's own
  JQL field names, which differ: `due` (not `due_date`), `issuetype`
  (not `issue_type`), `reporter` for "who filed this" (not `creator` --
  don't invent an alternate field name just because a query returns
  nothing). Never write a status literal into `--jql` (e.g.
  `status = 'Pending'`) unless you've actually seen that exact status
  name in a prior result -- a plausible guess doesn't error, it just
  silently returns zero misleading results. If a query built with the
  right, known field names still returns nothing, say exactly what you
  searched and ask, rather than silently swapping in a different field
  name and retrying.
- For subtask/description/component questions ("which tasks have no
  subtasks", "does this need frontend or backend work"), request the
  relevant fields via `--only` and reason over them yourself -- there is
  no separate classification tool, because "frontend" vs. "backend"
  isn't a fixed Jira field; it's inferred from this data.

If the result contains `"error"`, tell the user what went wrong in
plain language (invalid JQL, permission denied, etc.) instead of
retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
