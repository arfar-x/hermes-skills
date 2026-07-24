---
name: jira-worklog-delete
description: >-
  Permanently deletes a Jira worklog entry. Use for "delete that
  worklog", "remove the time I logged on PAY-123 by mistake". This is a
  destructive write operation gated behind explicit user confirmation.
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
    prompt: "Skip the confirm step before deleting a worklog? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira: Worklog Delete

**Write, gated, destructive.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py worklog_delete --issue_key PAY-123 --worklog_id 28459 --confirm
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key` and `--worklog_id` are required. Find `--worklog_id` via
the `jira-issue-summary` skill's `worklogs[].id`, or the id a prior
`jira-worklog` call returned. **This cannot be undone** -- there is no
restore.

This refuses to execute unless run with `--confirm` (enforced in code,
not just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true` is set:

1. State exactly which worklog you're about to permanently delete
   (issue, duration, description, date if known) and wait for the
   user's explicit yes.
2. Only then re-run the same command with `--confirm` appended.
3. If the result has `"requires_confirmation": true`, treat that as the
   tool declining to act -- relay `pending_action` to the user and ask,
   don't retry with `--confirm` on your own.

If you only need to fix a wrong duration/description/date rather than
remove the entry entirely, use `jira-worklog-edit` instead.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

Not sure whether the request is a new log, a fix to an existing entry,
or a deletion? Use `jira-log` instead -- it routes to whichever of
`jira-worklog`/`jira-worklog-edit`/`jira-worklog-delete` fits.

See `../jira/README.md` for architecture details and the full
environment-variable table.
