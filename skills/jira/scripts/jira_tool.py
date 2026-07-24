#!/usr/bin/env python3
"""Command-line dispatcher for the Jira Assistant skill's tools.

Hermes invokes skills by running shell commands (via its `terminal` /
`execute_code` sandbox), not by calling Python functions directly. This
script is the bridge: it exposes every tool in `tools/` as a subcommand
and always prints exactly one JSON document to stdout, so the agent can
parse the result the same way regardless of success or failure.

Usage:
    python scripts/jira_tool.py my_work [--project PAYKAN] [--all_projects]
    python scripts/jira_tool.py issue_summary --issue_key PAY-123 [--sections issue,worklogs]
    python scripts/jira_tool.py blockers --issue_key PAY-123
    python scripts/jira_tool.py search --jql "assignee = currentUser()" [--only summary,status,priority]
    python scripts/jira_tool.py worklog --issue_key PAY-123 --duration 2h \\
        --description "implementing validation" [--date 2026-07-20] [--confirm]
    python scripts/jira_tool.py transition --issue_key PAY-123 --status Review [--confirm]
    python scripts/jira_tool.py sprint [--board_id 3] [--project PAYKAN]
    python scripts/jira_tool.py kanban_status [--board_id 3] [--project PAYKAN]
    python scripts/jira_tool.py worklog_report [--since -14d] [--until ...] [--max_issues 50]
    python scripts/jira_tool.py list_fields
    python scripts/jira_tool.py worklog_edit --issue_key PAY-123 --worklog_id 28459 \\
        [--duration 2h] [--description "..."] [--date 2026-07-20] [--confirm]
    python scripts/jira_tool.py worklog_delete --issue_key PAY-123 --worklog_id 28459 [--confirm]
    python scripts/jira_tool.py triage [--project PAYKAN] [--parent_issue_types Story,Bug,Task]
    python scripts/jira_tool.py search_users --query john [--project PAYKAN] [--all_projects]
    python scripts/jira_tool.py create_issue --project PAYKAN --summary "..." \\
        --issue_type Story [--description "..."] [--parent_key PAYKAN-100] \\
        [--labels Frontend,UX] [--assignee_account_id ...] [--priority High] \\
        [--components API] [--confirm]
    python scripts/jira_tool.py edit_issue --issue_key PAYKAN-123 \\
        [--summary "..."] [--description "..."] [--labels Frontend] \\
        [--assignee_account_id ...] [--priority High] [--components API] [--confirm]

Every subcommand prints JSON only (never prose) and always exits 0 on a
handled error -- failures are reported as {"error": {...}} in the JSON
body, per this skill's "thin tools" design. A non-zero exit code means
the CLI invocation itself was malformed (e.g. unknown subcommand).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

from tools import (  # noqa: E402
    blockers,
    create_issue,
    edit_issue,
    issue_summary,
    kanban_status,
    list_fields,
    my_work,
    project_context,
    search,
    search_users,
    sprint,
    transition,
    triage,
    worklog,
    worklog_delete,
    worklog_edit,
    worklog_report,
)


def _add_common(parser: argparse.ArgumentParser, *, issue_key: bool = False) -> None:
    if issue_key:
        parser.add_argument("--issue_key", required=True, help="Issue key, e.g. PAY-123")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jira_tool", description="Jira Assistant tool dispatcher")
    subparsers = parser.add_subparsers(dest="tool", required=True)

    p = subparsers.add_parser("my_work", help="List unresolved issues assigned to the current user")
    p.add_argument(
        "--project",
        default=None,
        help="Scope to this project key. Falls back to JIRA_DEFAULT_PROJECT if omitted.",
    )
    p.add_argument(
        "--all_projects",
        action="store_true",
        help="Force an instance-wide search, ignoring --project and JIRA_DEFAULT_PROJECT.",
    )
    p.add_argument("--order_by", default="priority DESC, updated DESC")
    p.add_argument("--max_results", type=int, default=100)

    p = subparsers.add_parser("issue_summary", help="Full context for one issue")
    _add_common(p, issue_key=True)
    p.add_argument(
        "--sections",
        default=None,
        help="Comma-separated subset of issue,comments,worklogs,changelog,linked_issues "
        "to fetch and return. Omit for all -- pass a subset (e.g. 'issue') to skip "
        "fetching/returning the rest when you only need current fields.",
    )

    p = subparsers.add_parser("blockers", help="Blocking status and reasons for one issue")
    _add_common(p, issue_key=True)

    p = subparsers.add_parser("search", help="Run arbitrary JQL")
    p.add_argument("--jql", required=True)
    p.add_argument("--max_results", type=int, default=100)
    p.add_argument(
        "--fields",
        default=None,
        help="Comma-separated extra raw field IDs to request (e.g. from list_fields), "
        "always included in custom_fields regardless of --only",
    )
    p.add_argument(
        "--only",
        default=None,
        help="Comma-separated named fields to fetch and return (e.g. "
        "summary,status,priority) -- ask for exactly what you need instead of "
        "everything. Omit for the default set (everything except description "
        "and time-tracking fields). See SKILL.md for the full list of valid names.",
    )

    p = subparsers.add_parser("transition", help="Move an issue to a new status (write, gated)")
    _add_common(p, issue_key=True)
    p.add_argument("--status", required=True, help="Target status or transition name, e.g. Review")
    p.add_argument("--confirm", action="store_true", help="Only pass after the user has explicitly confirmed")

    p = subparsers.add_parser("worklog", help="Log time against an issue (write, gated)")
    _add_common(p, issue_key=True)
    p.add_argument("--duration", required=True, help='Jira-style duration, e.g. "2h", "1d 30m"')
    p.add_argument("--description", required=True)
    p.add_argument(
        "--date",
        default=None,
        help='When the work happened: relative ("-1d"), ISO date ("2026-07-20"), or ISO '
        "datetime. Resolve relative phrasing (e.g. \"last Tuesday\") to an actual calendar "
        "date yourself first. Default: now.",
    )
    p.add_argument("--confirm", action="store_true", help="Only pass after the user has explicitly confirmed")

    p = subparsers.add_parser("sprint", help="Active sprint, board, dates, and goal")
    p.add_argument("--board_id", type=int, default=None)
    p.add_argument(
        "--project",
        default=None,
        help="Resolve a board for this project (ignored if --board_id given). "
        "Falls back to JIRA_DEFAULT_PROJECT if omitted.",
    )

    p = subparsers.add_parser("kanban_status", help="Column breakdown for a kanban board")
    p.add_argument("--board_id", type=int, default=None)
    p.add_argument(
        "--project",
        default=None,
        help="Resolve a board for this project (ignored if --board_id given). "
        "Falls back to JIRA_DEFAULT_PROJECT if omitted.",
    )

    p = subparsers.add_parser(
        "worklog_report", help="Aggregate the current user's logged time over a date range"
    )
    p.add_argument("--since", default="-14d", help='Relative ("-14d") or ISO date/datetime. Default: -14d')
    p.add_argument("--until", default=None, help="Relative or ISO date/datetime. Default: now")
    p.add_argument("--max_issues", type=int, default=50)

    subparsers.add_parser("list_fields", help="Enumerate every field this Jira instance knows about")

    p = subparsers.add_parser("worklog_edit", help="Update an existing worklog entry (write, gated)")
    _add_common(p, issue_key=True)
    p.add_argument("--worklog_id", required=True, help="Worklog entry id, e.g. from issue_summary's worklogs[].id")
    p.add_argument("--duration", default=None, help='New duration, e.g. "2h" (omit to leave unchanged)')
    p.add_argument("--description", default=None, help="New description (omit to leave unchanged)")
    p.add_argument("--date", default=None, help="New date, same formats as worklog --date (omit to leave unchanged)")
    p.add_argument("--confirm", action="store_true", help="Only pass after the user has explicitly confirmed")

    p = subparsers.add_parser("worklog_delete", help="Permanently delete a worklog entry (write, gated)")
    _add_common(p, issue_key=True)
    p.add_argument("--worklog_id", required=True, help="Worklog entry id, e.g. from issue_summary's worklogs[].id")
    p.add_argument("--confirm", action="store_true", help="Only pass after the user has explicitly confirmed")

    p = subparsers.add_parser(
        "triage", help="Group unresolved parent issues with their labeled subtasks"
    )
    p.add_argument(
        "--project",
        default=None,
        help="Jira project key, e.g. PAYKAN. Falls back to JIRA_DEFAULT_PROJECT if omitted.",
    )
    p.add_argument(
        "--parent_issue_types",
        default=None,
        help='Comma-separated parent issue types. Default: "Story,Bug,Task"',
    )
    p.add_argument("--max_results", type=int, default=200)

    p = subparsers.add_parser(
        "project_context",
        help="Reference snapshot of a project: workflow statuses, assignable users, labels in use",
    )
    p.add_argument(
        "--project",
        default=None,
        help="Jira project key, e.g. PAY. Falls back to JIRA_DEFAULT_PROJECT if omitted.",
    )

    p = subparsers.add_parser("search_users", help="Look up users by name/email fragment")
    p.add_argument("--query", required=True, help='Name, username, or email fragment, e.g. "john"')
    p.add_argument(
        "--project",
        default=None,
        help="Scope to users assignable in this project (narrower, disambiguates common "
        "names). Falls back to JIRA_DEFAULT_PROJECT if omitted, then to an unscoped search.",
    )
    p.add_argument(
        "--all_projects",
        action="store_true",
        help="Force an unscoped, instance-wide search, ignoring --project and "
        "JIRA_DEFAULT_PROJECT both -- use to broaden after a scoped search finds no match.",
    )
    p.add_argument("--max_results", type=int, default=25)

    p = subparsers.add_parser(
        "create_issue", help="Create a new issue or subtask (write, gated)"
    )
    p.add_argument("--project", required=True, help="Project key, e.g. PAYKAN")
    p.add_argument("--summary", required=True)
    p.add_argument(
        "--issue_type", required=True, help='e.g. "Story", "Bug", "Task", "Sub-task"'
    )
    p.add_argument("--description", default=None)
    p.add_argument(
        "--parent_key", default=None, help='Required when --issue_type is "Sub-task"'
    )
    p.add_argument("--labels", default=None, help="Comma-separated labels, e.g. Frontend,UX")
    p.add_argument(
        "--assignee_account_id",
        default=None,
        help="A user's account_id -- resolve via search_users first, don't guess",
    )
    p.add_argument("--priority", default=None, help='e.g. "High"')
    p.add_argument("--components", default=None, help="Comma-separated component names")
    p.add_argument("--confirm", action="store_true", help="Only pass after the user has explicitly confirmed")

    p = subparsers.add_parser(
        "edit_issue", help="Update fields on an existing issue or subtask (write, gated)"
    )
    _add_common(p, issue_key=True)
    p.add_argument("--summary", default=None, help="New title (omit to leave unchanged)")
    p.add_argument("--description", default=None, help="New description (omit to leave unchanged)")
    p.add_argument("--labels", default=None, help="Comma-separated labels, replaces the existing list")
    p.add_argument(
        "--assignee_account_id",
        default=None,
        help="A user's account_id -- resolve via search_users first, don't guess",
    )
    p.add_argument("--priority", default=None, help='New priority name, e.g. "High"')
    p.add_argument("--components", default=None, help="Comma-separated component names, replaces the existing list")
    p.add_argument("--confirm", action="store_true", help="Only pass after the user has explicitly confirmed")

    return parser


def dispatch(args: argparse.Namespace):
    if args.tool == "my_work":
        return my_work.my_work(
            project=args.project,
            all_projects=args.all_projects,
            order_by=args.order_by,
            max_results=args.max_results,
        )
    if args.tool == "issue_summary":
        sections = args.sections.split(",") if args.sections else None
        return issue_summary.issue_summary(args.issue_key, sections=sections)
    if args.tool == "blockers":
        return blockers.blockers(args.issue_key)
    if args.tool == "search":
        extra_fields = args.fields.split(",") if args.fields else None
        only = args.only.split(",") if args.only else None
        return search.search(args.jql, max_results=args.max_results, fields=extra_fields, only=only)
    if args.tool == "transition":
        return transition.transition(args.issue_key, args.status, confirm=args.confirm)
    if args.tool == "worklog":
        return worklog.worklog(
            args.issue_key, args.duration, args.description, date=args.date, confirm=args.confirm
        )
    if args.tool == "sprint":
        return sprint.sprint(board_id=args.board_id, project=args.project)
    if args.tool == "kanban_status":
        return kanban_status.kanban_status(board_id=args.board_id, project=args.project)
    if args.tool == "worklog_report":
        return worklog_report.worklog_report(since=args.since, until=args.until, max_issues=args.max_issues)
    if args.tool == "list_fields":
        return list_fields.list_fields()
    if args.tool == "worklog_edit":
        return worklog_edit.worklog_edit(
            args.issue_key,
            args.worklog_id,
            duration=args.duration,
            description=args.description,
            date=args.date,
            confirm=args.confirm,
        )
    if args.tool == "worklog_delete":
        return worklog_delete.worklog_delete(args.issue_key, args.worklog_id, confirm=args.confirm)
    if args.tool == "triage":
        parent_types = args.parent_issue_types.split(",") if args.parent_issue_types else None
        return triage.triage(
            project=args.project, parent_issue_types=parent_types, max_results=args.max_results
        )
    if args.tool == "project_context":
        return project_context.project_context(project=args.project)
    if args.tool == "search_users":
        return search_users.search_users(
            args.query, project=args.project, all_projects=args.all_projects, max_results=args.max_results
        )
    if args.tool == "create_issue":
        labels = args.labels.split(",") if args.labels else None
        components = args.components.split(",") if args.components else None
        return create_issue.create_issue(
            args.project,
            args.summary,
            args.issue_type,
            description=args.description,
            parent_key=args.parent_key,
            labels=labels,
            assignee_account_id=args.assignee_account_id,
            priority=args.priority,
            components=components,
            confirm=args.confirm,
        )
    if args.tool == "edit_issue":
        labels = args.labels.split(",") if args.labels else None
        components = args.components.split(",") if args.components else None
        return edit_issue.edit_issue(
            args.issue_key,
            summary=args.summary,
            description=args.description,
            labels=labels,
            assignee_account_id=args.assignee_account_id,
            priority=args.priority,
            components=components,
            confirm=args.confirm,
        )
    raise AssertionError(f"Unhandled tool: {args.tool}")  # unreachable: argparse enforces choices


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = dispatch(args)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
