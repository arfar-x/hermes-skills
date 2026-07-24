---
name: jira-edit-issue
description: >-
  Updates fields (summary, description, labels, assignee, priority,
  components) on an existing Jira issue or subtask. Use for "rename
  PAY-123", "reassign PAY-123 to John", "add the Backend label to
  PAY-101". This is a write operation gated behind explicit user
  confirmation. For moving an issue between statuses, use jira-status
  instead.
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
    prompt: "Skip the confirm step before editing tickets? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira: Edit Issue

**Write, gated.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py edit_issue --issue_key PAYKAN-123 \
  --summary "New title" --confirm
```

Works the same way on a subtask -- just pass the subtask's own
`--issue_key`.

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key` is required; at least one of `--summary`, `--description`,
`--labels` (comma-separated, replaces the existing list), `--assignee_account_id`,
`--priority`, `--components` (comma-separated, replaces the existing list)
must be given. Omitted fields are left unchanged.

## Assignee

`--assignee_account_id` needs a Jira `account_id`, not a display name --
resolve one via `jira-search-users` first rather than guessing.

## Confirmation

This refuses to execute unless run with `--confirm` (enforced in code, not
just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true` is set:

1. State exactly which fields you're about to change and to what value,
   and wait for the user's explicit yes.
2. Only then re-run the same command with `--confirm` appended.
3. If the result has `"requires_confirmation": true`, treat that as the
   tool declining to act -- relay `pending_action` to the user and ask,
   don't retry with `--confirm` on your own.

If the result contains `"error"`, tell the user what went wrong in plain
language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
