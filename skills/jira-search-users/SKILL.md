---
name: jira-search-users
description: >-
  Looks up Jira users by name/email fragment and returns their account_id.
  Use to resolve a person's name (e.g. "John") into the account_id JQL and
  create_issue/edit_issue need for assignee filters/fields -- never guess
  or invent an account_id.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, lookup]
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

# Jira: Search Users

**Read-only.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py search_users --query john
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

## Why this exists

JQL and `create_issue`/`edit_issue` need a Jira `account_id` to filter or
set an assignee -- not a display name. This tool is the one place that
turns "John" into that id, so you never have to guess one or fabricate a
JQL clause like `assignee = "John"` that may not match Jira's actual user
record.

## Using the result

- `count: 0` -- no match. Tell the user, don't guess a name variant.
- `count: 1` -- use `users[0].account_id`.
- `count > 1` -- ask the user which person they meant (show
  `display_name`/`email` for each) rather than picking the first result.

## Example

**"Find John's tasks that I reported, due tomorrow."**
1. `search_users --query john` to resolve John to an `account_id` (ask the
   user to disambiguate if more than one match).
2. Resolve "tomorrow" to an actual calendar date yourself.
3. `search --jql "assignee = <account_id> AND reporter = currentUser() AND due = <date>"`
   via `jira-issues`/`jira`.

If the result contains `"error"`, tell the user what went wrong in plain
language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
