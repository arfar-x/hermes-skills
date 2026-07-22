"""worklog_report: aggregate the current user's logged time over a date
range, compared against each touched issue's original estimate.

Thin tool: finds candidate issues via JQL (``worklogDate``/``worklogAuthor``),
then pulls each candidate's worklogs and filters them client-side to the
exact window and to entries authored by the current user -- JQL's
``worklogDate`` only guarantees *an* entry exists somewhere in range, not
which ones, so exact totals require this second pass. No prioritization,
"what took long" analysis, or summarization happens here -- every matched
worklog's comment is returned as-is for the LLM to reason over.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

from lib.jira_client import JiraClient, get_client
from lib.models import Issue, Worklog
from lib.utils import InvalidDateError, jql_date_literal, parse_jira_timestamp, parse_jql_date
from tools._common import ToolInputError, run_tool

_REPORT_FIELDS = ["summary", "status", "timeoriginalestimate", "timespent", "timeestimate"]


def _resolve_window(since: str, until: Optional[str]) -> Tuple[dt.datetime, Optional[dt.datetime]]:
    """Parse and validate the ``[since, until]`` window, or raise ToolInputError."""
    try:
        since_dt = parse_jql_date(since)
        until_dt = parse_jql_date(until) if until else None
    except InvalidDateError as exc:
        raise ToolInputError(str(exc)) from exc
    if until_dt is not None and until_dt <= since_dt:
        raise ToolInputError("'until' must be after 'since'.")
    return since_dt, until_dt


def _build_jql(since: str, until: Optional[str]) -> str:
    """Candidate-issue JQL: cheap, day-granularity pre-filter via Jira itself."""
    jql = f"worklogDate >= {jql_date_literal(since)} AND worklogAuthor = currentUser()"
    if until:
        jql += f" AND worklogDate <= {jql_date_literal(until)}"
    return jql


def _worklogs_in_window(
    worklogs: List[Worklog],
    *,
    author_display_name: Optional[str],
    since_dt: dt.datetime,
    until_dt: Optional[dt.datetime],
) -> List[Worklog]:
    """Exact per-entry filter: JQL only guarantees *an* entry is in range."""
    matched = []
    for wl in worklogs:
        if wl.author != author_display_name or not wl.started:
            continue
        try:
            started_dt = parse_jira_timestamp(wl.started)
        except InvalidDateError:
            continue
        if started_dt < since_dt or (until_dt is not None and started_dt > until_dt):
            continue
        matched.append(wl)
    return matched


def _issue_entry(issue: Issue, matched: List[Worklog]) -> Dict[str, Any]:
    estimate = issue.original_estimate_seconds
    logged_seconds = sum(wl.time_spent_seconds for wl in matched)
    return {
        "key": issue.key,
        "url": issue.url,
        "summary": issue.summary,
        "status": issue.status,
        "original_estimate_seconds": estimate,
        "logged_seconds": logged_seconds,
        "delta_seconds": (logged_seconds - estimate) if estimate is not None else None,
        "worklogs": [wl.to_dict() for wl in matched],
    }


def _collect_report_issues(
    client: JiraClient, candidate_issues: List[Issue], *, since_dt: dt.datetime, until_dt: Optional[dt.datetime]
) -> List[Dict[str, Any]]:
    author_display_name = client.get_current_user().display_name
    entries = []
    for issue in candidate_issues:
        matched = _worklogs_in_window(
            client.get_worklogs(issue.key),
            author_display_name=author_display_name,
            since_dt=since_dt,
            until_dt=until_dt,
        )
        if matched:
            entries.append(_issue_entry(issue, matched))
    entries.sort(key=lambda entry: entry["logged_seconds"], reverse=True)
    return entries


def worklog_report(
    since: str = "-14d",
    until: Optional[str] = None,
    max_issues: int = 50,
) -> Dict[str, Any]:
    """Aggregate the current user's worklogs between ``since`` and ``until``.

    Args:
        since: Start of the window -- a JQL-style relative date (``"-14d"``,
            ``"-2w"``) or an ISO date/datetime. Defaults to the last 14 days.
        until: End of the window (same formats). Defaults to now.
        max_issues: Safety cap on the number of candidate issues scanned.

    Returns:
        ``{"since": ..., "until": ..., "total_logged_seconds": N,
           "total_original_estimate_seconds": N, "total_delta_seconds": N,
           "issue_count": N, "issues": [{"key", "summary", "status",
           "original_estimate_seconds", "logged_seconds", "delta_seconds",
           "worklogs": [...]}, ...]}`` (``issues`` sorted by logged time,
        most first).
    """

    def _run() -> Dict[str, Any]:
        since_dt, until_dt = _resolve_window(since, until)

        client = get_client()
        candidate_issues = client.search(
            _build_jql(since, until), fields=_REPORT_FIELDS, max_results=max_issues
        )
        report_issues = _collect_report_issues(
            client, candidate_issues, since_dt=since_dt, until_dt=until_dt
        )

        return {
            "since": since,
            "until": until,
            "total_logged_seconds": sum(i["logged_seconds"] for i in report_issues),
            "total_original_estimate_seconds": sum(
                i["original_estimate_seconds"] or 0 for i in report_issues
            ),
            "total_delta_seconds": sum(i["logged_seconds"] for i in report_issues)
            - sum(i["original_estimate_seconds"] or 0 for i in report_issues),
            "issue_count": len(report_issues),
            "issues": report_issues,
        }

    return run_tool("worklog_report", _run)
