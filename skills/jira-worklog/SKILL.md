---
name: jira-worklog
description: >-
  Logs time against a Jira issue. Use for "log 2h on PAY-123" or "I
  spent 30 minutes on PAY-123 today". This is a write operation gated
  behind explicit user confirmation.
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
    prompt: "Skip the confirm step before logging work? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira: Worklog

**Write, gated.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py worklog --issue_key PAY-123 --duration 2h --description "implementing validation" --confirm
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key`, `--duration` (Jira-style, e.g. `2h`, `1d 30m`), and
`--description` are required. This refuses to execute unless run with
`--confirm` (enforced in code, not just prompted). Unless
`JIRA_AUTO_CONFIRM_WRITES=true` is set:

1. State exactly what you're about to log and wait for the user's
   explicit yes.
2. Only then re-run the same command with `--confirm` appended.
3. If the result has `"requires_confirmation": true`, treat that as the
   tool declining to act -- relay `pending_action` to the user and ask,
   don't retry with `--confirm` on your own.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
