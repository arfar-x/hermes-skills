"""my_work: list unresolved issues assigned to the current user.

Thin tool: builds a JQL query, calls the shared JiraClient, and returns
structured JSON. Performs no prioritization or summarization -- that is
left entirely to the LLM.
"""

from __future__ import annotations

from typing import Any, Dict, List

from lib.jira_client import get_client, resolve_issue_fields
from lib.utils import is_issue_blocked
from tools._common import run_tool

#: Statuses considered "unresolved" for the purposes of my_work(). Jira's
#: built-in `resolution = Unresolved` predicate is used instead of a
#: status allowlist so this stays correct across differently configured
#: workflows.
_UNRESOLVED_JQL = "assignee = currentUser() AND resolution = Unresolved"

#: my_work()'s output is a fixed, small shape -- fetch exactly the fields
#: it uses (plus "links", needed only to compute "blocked") instead of
#: Jira's full default field set.
_MY_WORK_FIELDS, _ = resolve_issue_fields(
    ["summary", "priority", "status", "updated"], always_fetch=["links"]
)


def my_work(order_by: str = "priority DESC, updated DESC", max_results: int = 100) -> List[Dict[str, Any]]:
    """Return every unresolved issue assigned to the authenticated user.

    Args:
        order_by: JQL ORDER BY clause. Defaults to priority then recency.
        max_results: Safety cap on the number of issues returned.

    Returns:
        A JSON list of issue summaries, e.g.::

            [{"key": "PAY-123", "url": "https://jira.example.com/browse/PAY-123",
              "summary": "...", "priority": "High", "status": "In Progress",
              "updated": "...", "blocked": false}]
    """

    def _run() -> List[Dict[str, Any]]:
        client = get_client()
        jql = _UNRESOLVED_JQL
        if order_by:
            jql = f"{jql} ORDER BY {order_by}"
        issues = client.search(jql, fields=_MY_WORK_FIELDS, max_results=max_results)
        return [
            {
                "key": issue.key,
                "url": issue.url,
                "summary": issue.summary,
                "priority": issue.priority,
                "status": issue.status,
                "updated": issue.updated,
                "blocked": is_issue_blocked(issue),
            }
            for issue in issues
        ]

    return run_tool("my_work", _run)
