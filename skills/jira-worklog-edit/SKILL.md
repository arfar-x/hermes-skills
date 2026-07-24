---
name: jira-worklog-edit
description: >-
  Updates an existing Jira worklog entry's duration, description, or
  date. Use for "fix that worklog", "I logged the wrong date, change it
  to Tuesday", "change the description on that time log". This is a
  write operation gated behind explicit user confirmation.
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
    prompt: "Skip the confirm step before editing a worklog? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira: Worklog Edit

**Write, gated.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py worklog_edit --issue_key PAY-123 --worklog_id 28459 \
  [--duration 2h] [--description "..."] [--date 2026-07-20] --confirm
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key` and `--worklog_id` are required; at least one of
`--duration`/`--description`/`--date` must also be given (omitted fields
are left unchanged). Find `--worklog_id` via the `jira-issue-summary`
skill's `worklogs[].id`, or from the id a prior `jira-worklog` call
returned.

This refuses to execute unless run with `--confirm` (enforced in code,
not just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true` is set:

1. State exactly what you're about to change (old vs. new
   duration/description/date) and wait for the user's explicit yes.
2. Only then re-run the same command with `--confirm` appended.
3. If the result has `"requires_confirmation": true`, treat that as the
   tool declining to act -- relay `pending_action` to the user and ask,
   don't retry with `--confirm` on your own.

`--date` accepts the same formats as `jira-worklog`'s `--date` (relative,
ISO date, or ISO datetime) -- resolve relative day-names ("last Tuesday")
to an actual calendar date yourself first.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

Not sure whether the request is a new log, a fix to an existing entry,
or a deletion? Use `jira-log` instead -- it routes to whichever of
`jira-worklog`/`jira-worklog-edit`/`jira-worklog-delete` fits.

See `../jira/README.md` for architecture details and the full
environment-variable table.
