---
name: jira-my-work
description: >-
  Lists unresolved Jira issues assigned to the current user, ordered by
  priority and recency. Use for "what should I work on next", "what are
  my open tickets", "summarize my tickets".
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets]
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

# Jira: My Work

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py my_work [--project PAY] [--all_projects] \
  [--order_by "priority DESC, updated DESC"] [--max_results 100]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

Scoped to a project by default -- `--project`, or `JIRA_DEFAULT_PROJECT`
if `--project` is omitted -- so results stay to the project actually
being worked in instead of mixing in every other project the user has
issues assigned in. Only pass `--all_projects` (which ignores both
`--project` and `JIRA_DEFAULT_PROJECT`) if the user has actually asked to
broaden beyond their current project; don't reach for it just because a
scoped result looked short.

Prints one JSON document: `{"project": "PAY" | null, "count": N,
"issues": [...]}` -- `issues` items have key, summary, status, priority,
`blocked`, `updated`, etc. `project` is the scope actually used (`null`
if unscoped), so always check it before reporting results, especially if
`JIRA_DEFAULT_PROJECT` might have applied silently. Never invent or
fabricate issue data -- everything you state must come from this JSON.
Reason over the list (priority, status, `blocked`, staleness) and
recommend the best candidate in prose; don't just dump the JSON.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
