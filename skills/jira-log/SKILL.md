---
name: jira-log
description: >-
  Single entry point for worklog actions on a Jira issue -- logging new
  time, fixing an existing entry's duration/description/date, or
  deleting one. Routes to the right underlying action based on what's
  being asked. Use for "log 2h on PAY-123", "fix that worklog, wrong
  day", "delete that worklog I logged by mistake". Write operations,
  gated behind explicit user confirmation.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, worklog, write]
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
    prompt: "Skip the confirm step before logging/editing/deleting worklogs? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira: Log

**Write, gated.** This skill routes to whichever of `worklog`/
`worklog_edit`/`worklog_delete` fits the request -- run from this
skill's directory:

## 1. Figure out the intent

- New time being logged ("log 2h on PAY-123", "I spent 30m on PAY-123
  today") -> **log** (below).
- An existing entry is wrong ("fix that worklog", "wrong date, should be
  Tuesday", "change the description on that time log") -> **edit**
  (below). Find `--worklog_id` via `jira-issue-summary`'s
  `worklogs[].id`, or the id a prior log call returned.
- An entry should be removed entirely ("delete that worklog", "remove
  the time I logged by mistake") -> **delete** (below), not edit.

## 2. Run the matching command

```bash
# Log new time
python3 ../jira/scripts/jira_tool.py worklog --issue_key PAY-123 --duration 2h \
  --description "implementing validation" [--date 2026-07-20] --confirm

# Fix an existing entry (at least one of --duration/--description/--date;
# omitted fields are left unchanged)
python3 ../jira/scripts/jira_tool.py worklog_edit --issue_key PAY-123 --worklog_id 28459 \
  [--duration 2h] [--description "..."] [--date 2026-07-20] --confirm

# Permanently delete an entry -- cannot be undone
python3 ../jira/scripts/jira_tool.py worklog_delete --issue_key PAY-123 --worklog_id 28459 --confirm
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--date` (log/edit) accepts a relative offset (`-1d`), an ISO date, or a
full ISO datetime -- **resolve relative day-names ("last Tuesday",
"yesterday") to an actual calendar date yourself first**; these tools
don't parse natural-language dates and never silently log against
"today" when the user meant a different day.

## 3. Confirmation gate applies to all three

Every command above refuses to execute unless run with `--confirm`
(enforced in code, not just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true`
is set:

1. State exactly what you're about to do -- for log/edit, include the
   resolved date if not today; for edit, state old vs. new
   duration/description/date; for delete, state the specific entry
   (issue, duration, date, description if known), since it's
   irreversible -- and wait for the user's explicit yes.
2. Only then re-run the same command with `--confirm` appended.
3. If a result has `"requires_confirmation": true`, treat that as the
   tool declining to act -- relay `pending_action` to the user and ask,
   don't retry with `--confirm` on your own.

Already know exactly which action you need? `jira-worklog`/
`jira-worklog-edit`/`jira-worklog-delete` call the same underlying
commands directly, without the routing step.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
