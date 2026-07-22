---
name: jira
description: >-
  High-level Jira assistant. Answers questions like "what should I work
  on next", "summarize my tickets", "what's blocking PAY-123", logs work,
  and moves tickets between statuses -- by calling structured Jira tools
  and reasoning over their JSON output, never by guessing or inventing
  ticket data. Use whenever the user asks about Jira issues, sprints,
  boards, worklogs, or ticket status.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, tools]
    category: software-development
    requires_toolsets: [terminal]
required_environment_variables:
  - name: JIRA_BASE_URL
    prompt: "Jira base URL (e.g. https://jira.mycompany.com)"
    required_for: all functionality
  - name: JIRA_USERNAME
    prompt: "Jira username"
    required_for: all functionality
  - name: JIRA_PASSWORD
    prompt: "Jira password"
    required_for: all functionality
  - name: JIRA_AUTO_CONFIRM_WRITES
    prompt: "Skip the confirm step before logging work / transitioning tickets? (true/false)"
    required_for: optional, defaults to false (asks before every write)
---

# Jira Assistant

## When to use

Any time the user asks about their Jira work: what to work on next,
summarizing tickets, checking blockers, searching issues by JQL, logging
time, moving a ticket's status, or checking the active sprint.

## How it works

This skill is a thin CLI wrapper (`scripts/jira_tool.py`) around a typed
Jira REST client (`lib/jira_client.py`). The CLI **only** validates input,
calls Jira, and prints one JSON document to stdout -- it never
summarizes, prioritizes, or explains. **All reasoning is your job.**

Run it with `terminal` from this skill's directory:

```
python3 scripts/jira_tool.py <tool> [--flags...]
```

(First-time setup, once per environment: `pip install -r requirements.txt`.)

## Core rules

1. **Always call a tool before answering a Jira question.** Never answer
   from memory or assumption -- if you haven't run the relevant command
   this turn, run it first.
2. **Never invent issue information.** Every key, summary, status,
   priority, comment, or date you state must come from the JSON a tool
   returned.
3. **Never fabricate blockers.** Only report a blocker if `blockers`'s
   `reasons` array (or `my_work`/`search`'s `blocked` field) actually
   contains it. If `"blocked": false`, say so -- don't invent a plausible
   one.
4. **Never guess ticket status.** Re-fetch via `issue_summary`, `my_work`,
   or `search` rather than trusting stale conversation history.
5. **Write operations require confirmation.** `transition` and `worklog`
   refuse to execute unless run with `--confirm` (this is enforced in
   code, not just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true` is
   set:
   - State exactly what you're about to do and wait for the user's
     explicit yes.
   - Only then re-run the same command with `--confirm` appended.
   - If a result has `"requires_confirmation": true`, treat that as the
     tool declining to act -- relay `pending_action` to the user and ask.
6. **Chain tool calls when needed.** E.g. "what should I work on next,
   and is anything blocking it?" = `my_work` first, then `blockers` on
   the top candidate(s).
7. **If a result contains `"error"`,** tell the user what went wrong in
   plain language (not found, permission denied, invalid JQL, etc.)
   instead of retrying silently or fabricating a result.

## Commands

```bash
# Unresolved issues assigned to the current user
python3 scripts/jira_tool.py my_work

# Full context for one issue: fields, comments, worklogs, changelog, links
python3 scripts/jira_tool.py issue_summary --issue_key PAY-123

# Blocking status + reasons for one issue
python3 scripts/jira_tool.py blockers --issue_key PAY-123

# Arbitrary JQL search
python3 scripts/jira_tool.py search --jql "assignee = currentUser() AND updated <= -14d"

# Active sprint / board / dates / goal
python3 scripts/jira_tool.py sprint

# Log time (write, gated -- see rule 5)
python3 scripts/jira_tool.py worklog --issue_key PAY-123 --duration 2h \
  --description "implementing validation" --confirm

# Move to a status (write, gated -- see rule 5); target status/transition
# name is resolved automatically, no need to know Jira's internal IDs
python3 scripts/jira_tool.py transition --issue_key PAY-123 --status Review --confirm
```

## Examples

**"What should I work on next?"**
Run `my_work`. Reason over the returned list (priority, status, `blocked`,
staleness) and recommend the best candidate in prose -- don't just dump
the JSON.

**"What's blocking PAY-412?"**
Run `blockers --issue_key PAY-412`. If `blocked: true`, summarize
`reasons` in a sentence. If `false`, say nothing is blocking it.

**"Summarize PAY-412."**
Run `issue_summary --issue_key PAY-412`. Produce a concise natural-
language summary of status, recent activity, and any linked work.

**"Log 2h on PAY-412 for implementing validation."**
First confirm with the user ("I'll log 2h on PAY-412: 'implementing
validation' — confirm?"), then run `worklog ... --confirm`.

**"Move PAY-412 to Review."**
Confirm with the user, then run `transition --issue_key PAY-412 --status Review --confirm`.

**"Which of my tickets haven't been updated recently?"**
Run `search --jql "assignee = currentUser() AND resolution = Unresolved AND updated <= -14d"`.

## Reference

See `README.md` in this skill directory for architecture details, the
full environment-variable table, and how to run the test suite
(`pytest`, 56 tests covering the client, config validation, and every
tool's success/error/confirmation paths).
