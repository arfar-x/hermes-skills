"""my_work: list unresolved issues assigned to the current user.

Thin tool: builds a JQL query, calls the shared JiraClient, and returns
structured JSON. Performs no prioritization or summarization -- that is
left entirely to the LLM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def my_work(
    project: Optional[str] = None,
    all_projects: bool = False,
    order_by: str = "priority DESC, updated DESC",
    max_results: int = 100,
) -> Dict[str, Any]:
    """Return every unresolved issue assigned to the authenticated user.

    Args:
        project: Project key to scope the search to. Falls back to
            ``JIRA_DEFAULT_PROJECT`` if unset. Pass this (or set the
            default) to keep results to the project you're actually
            working in, rather than every project you're assigned issues
            across.
        all_projects: Force an instance-wide, unscoped search even if a
            project would otherwise resolve. Only set this when the user
            has actually asked to broaden beyond their current project.
        order_by: JQL ORDER BY clause. Defaults to priority then recency.
        max_results: Safety cap on the number of issues returned.

    Returns:
        ``{"project": "PAY" | null, "count": N, "issues": [...]}`` --
        ``project`` is the scope actually used (``null`` if
        ``all_projects=True`` or if neither an explicit project nor
        ``JIRA_DEFAULT_PROJECT`` resolved), so the caller always knows
        whether this was scoped or instance-wide. Each issue::

            {"key": "PAY-123", "url": "https://jira.example.com/browse/PAY-123",
             "summary": "...", "priority": "High", "status": "In Progress",
             "updated": "...", "blocked": false}
    """

    def _run() -> Dict[str, Any]:
        client = get_client()
        resolved_project = None if all_projects else client.resolve_project(project)

        jql = _UNRESOLVED_JQL
        if resolved_project:
            jql = f"project = {resolved_project} AND {jql}"
        if order_by:
            jql = f"{jql} ORDER BY {order_by}"

        issues = client.search(jql, fields=_MY_WORK_FIELDS, max_results=max_results)
        issue_dicts = [
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
        return {"project": resolved_project, "count": len(issue_dicts), "issues": issue_dicts}

    return run_tool("my_work", _run)
