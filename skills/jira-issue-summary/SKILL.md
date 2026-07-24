---
name: jira-issue-summary
description: >-
  Full context for one Jira issue: fields, comments, worklogs, changelog,
  and links, as one document. Use for "summarize PAY-123" or "what's the
  status of PAY-123".
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

# Jira: Issue Summary

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py issue_summary --issue_key PAY-123 [--sections issue,worklogs]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key` is required. Prints one JSON document combining fields,
comments, worklogs, changelog, and links. Never invent or fabricate
issue data -- produce a concise natural-language summary of status,
recent activity, and any linked work, using only what the JSON returned.

`--sections` (optional, comma-separated subset of `issue`, `comments`,
`worklogs`, `changelog`, `linked_issues`) limits what's fetched and
returned -- omit it for everything, or narrow it (e.g. `--sections issue`
for just current fields) when the question doesn't need the full
history, to save tokens.

If the result contains `"error"`, tell the user what went wrong in
plain language (not found, permission denied, etc.) instead of
retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
