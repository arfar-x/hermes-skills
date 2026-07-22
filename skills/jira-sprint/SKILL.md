---
name: jira-sprint
description: >-
  Active sprint, board, dates, and goal. Use for "what's the current
  sprint", "when does this sprint end", "what's the sprint goal".
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, sprint, board]
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

# Jira: Sprint

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py sprint [--board_id 42]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--board_id` is optional -- omit it to use the first board visible to
the authenticated user. Prints one JSON document with the active
sprint's board, dates, and goal. Never invent data not present in the
JSON.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
