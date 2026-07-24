---
name: jira-create-issue
description: >-
  Creates a new Jira issue -- a parent work item (Story/Bug/Task/Epic) or
  a subtask under one. Use for "create a bug for X", "add a frontend
  subtask under PAY-100". This is a write operation gated behind explicit
  user confirmation.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, write]
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
  - name: JIRA_AUTO_CONFIRM_WRITES
    prompt: "Skip the confirm step before creating tickets? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira: Create Issue

**Write, gated.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py create_issue --project PAYKAN --summary "Fix checkout crash" \
  --issue_type Bug --confirm
```

Creating a subtask under an existing parent -- same tool, add `--parent_key`
and use `--issue_type Sub-task`:

```bash
python3 ../jira/scripts/jira_tool.py create_issue --project PAYKAN --summary "Build checkout UI" \
  --issue_type Sub-task --parent_key PAYKAN-100 --labels Frontend --confirm
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--project`, `--summary`, and `--issue_type` are required. `--issue_type
Sub-task` requires `--parent_key`. Optional: `--description`, `--labels`
(comma-separated), `--assignee_account_id`, `--priority`, `--components`
(comma-separated).

## Assignee

`--assignee_account_id` needs a Jira `account_id`, not a display name --
resolve one via `jira-search-users` first (e.g. `search_users --query john`)
rather than guessing.

## Confirmation

This refuses to execute unless run with `--confirm` (enforced in code, not
just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true` is set:

1. State exactly what you're about to create (project, summary, type, and
   parent if it's a subtask) and wait for the user's explicit yes.
2. Only then re-run the same command with `--confirm` appended.
3. If the result has `"requires_confirmation": true`, treat that as the
   tool declining to act -- relay `pending_action` to the user and ask,
   don't retry with `--confirm` on your own.

If the result contains `"error"`, tell the user what went wrong in plain
language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
