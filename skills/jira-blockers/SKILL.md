---
name: jira-blockers
description: >-
  Blocking status and reasons for one Jira issue (status flags,
  unresolved "blocked by" links, flagged comments). Use for "what's
  blocking PAY-123" or "is PAY-123 blocked".
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

# Jira: Blockers

Read-only. Run from this skill's directory via `terminal`:

```bash
python3 ../jira/scripts/jira_tool.py blockers --issue_key PAY-123
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key` is required. Prints `{"blocked": bool, "reasons": [...]}`.
Only report a blocker if `reasons` actually contains it -- if
`"blocked": false`, say so; don't invent a plausible one.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
