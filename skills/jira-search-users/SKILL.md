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
  - name: JIRA_DEFAULT_PROJECT
    prompt: "Default Jira project key (e.g. PAY), to scope user lookups when --project isn't given"
    required_for: optional -- narrows lookups and disambiguates common names; unscoped search is used if unset
---

# Jira: Search Users

**Read-only.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py search_users --query john [--project PAY] [--all_projects]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

## Why this exists

JQL and `create_issue`/`edit_issue` need a Jira `account_id` to filter or
set an assignee -- not a display name. This tool is the one place that
turns "John" into that id, so you never have to guess one or fabricate a
JQL clause like `assignee = "John"` that may not match Jira's actual user
record.

## Scoping to a project

A name search across the whole Jira instance can be ambiguous -- e.g. two
different people named "Sam" instance-wide, only one of whom is actually
on the project you're asking about. `--project` scopes the search to users
assignable in that project instead, which is both narrower and usually
resolves the ambiguity outright. Prefer scoping whenever the question is
already about a specific project (from context, an issue key already
mentioned, or `JIRA_DEFAULT_PROJECT`) -- fall back to an unscoped search
only when no project is known.

## Using the result

The response's `project` field tells you what scope was actually used
(`null` means unscoped) -- use it, don't just remember what you passed in,
since an omitted `--project` can still resolve to `JIRA_DEFAULT_PROJECT`.

- `count: 0` and `project` is set -- don't conclude there's no such user.
  Tell the user no match was found *in that project* and ask whether to
  broaden to an instance-wide search; only retry with `--all_projects` if
  they say yes (`--all_projects` is required to truly go unscoped --
  omitting `--project` alone isn't enough when `JIRA_DEFAULT_PROJECT` is
  set, since it would still apply).
- `count: 0` and `project` is `null` -- no match anywhere. Tell the user,
  don't guess a name variant.
- `count: 1` -- use `users[0].account_id`.
- `count > 1` and `project` is `null` and a project is known/relevant --
  retry scoped first; it may resolve on its own.
- `count > 1` otherwise -- ask the user which person they meant (show
  `display_name`/`email` for each) rather than picking the first result.

## Example

**"Find John's tasks that I reported, due tomorrow."**
1. `search_users --query john` (add `--project PAY` if the project is
   known/relevant) to resolve John to an `account_id` (ask the user to
   disambiguate if more than one match, after trying a project-scoped
   search).
2. Resolve "tomorrow" to an actual calendar date yourself.
3. `search --jql "assignee = <account_id> AND reporter = currentUser() AND due = <date>"`
   via `jira-issues`/`jira`.

If the result contains `"error"`, tell the user what went wrong in plain
language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
