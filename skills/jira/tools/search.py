"""search: run an arbitrary JQL query and return structured issue data.

Thin tool: validates the JQL is non-empty, delegates to the shared
JiraClient, and returns issue JSON. Query construction/interpretation is
the LLM's responsibility; this tool never rewrites or infers JQL.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import get_client, resolve_issue_fields
from lib.utils import is_issue_blocked
from tools._common import require_str, run_tool

#: Fetched from Jira for "blocked" detection regardless of `only`, without
#: forcing "status"/"links" into the output unless the caller asked for
#: them too -- see lib.utils.blocking_reasons().
_BLOCKED_DETECTION_FIELDS = ["status", "links"]


def search(
    jql: str,
    max_results: int = 100,
    fields: Optional[List[str]] = None,
    only: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run a JQL query and return matching issues.

    Args:
        jql: A valid JQL query string, e.g.
            ``"project = PAY AND status = 'In Progress'"``.
        max_results: Safety cap on the number of issues returned.
        fields: Extra raw Jira field IDs to request (e.g. a custom field ID
            discovered via ``list_fields``, like ``"customfield_10056"`` for
            a "Figma Link" field). Always included in each issue's
            ``custom_fields``, regardless of ``only``.
        only: Which named issue fields to fetch from Jira and include in
            the response -- the token-efficiency lever: ask for exactly
            what you need instead of everything. Valid names: ``summary``,
            ``status``, ``priority``, ``issue_type``, ``assignee``,
            ``reporter``, ``updated``, ``created``, ``due_date``,
            ``labels``, ``links``, ``description``, ``components``,
            ``subtasks``, ``original_estimate_seconds``,
            ``time_spent_seconds``, ``remaining_estimate_seconds``.
            Defaults to every field except ``description`` and the three
            time-tracking fields when omitted. Pass ``description``
            explicitly (e.g. ``only=["summary", "description"]``) only
            when you actually need description text for a handful of
            issues -- for a single issue, prefer ``issue_summary`` or
            ``get_issue`` instead of a detailed search.

    Returns:
        ``{"jql": "...", "count": N, "issues": [...]}`` -- each issue always
        includes ``key``, ``url``, ``custom_fields``, and ``blocked``,
        regardless of ``only``.
    """

    def _run() -> Dict[str, Any]:
        query = require_str(jql, "jql")
        client = get_client()
        jira_fields, output_keys = resolve_issue_fields(only, always_fetch=_BLOCKED_DETECTION_FIELDS)
        requested_fields = jira_fields + list(fields or [])
        issues = client.search(query, max_results=max_results, fields=requested_fields)
        issue_dicts: List[Dict[str, Any]] = []
        for issue in issues:
            d = issue.to_dict(only=output_keys)
            d["blocked"] = is_issue_blocked(issue)
            issue_dicts.append(d)
        return {"jql": query, "count": len(issue_dicts), "issues": issue_dicts}

    return run_tool("search", _run)
