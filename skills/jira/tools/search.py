"""search: run an arbitrary JQL query and return structured issue data.

Thin tool: validates the JQL is non-empty, delegates to the shared
JiraClient, and returns issue JSON. Query construction/interpretation is
the LLM's responsibility; this tool never rewrites or infers JQL.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import COMPACT_ISSUE_FIELDS, DEFAULT_ISSUE_FIELDS, get_client
from lib.utils import is_issue_blocked
from tools._common import require_str, run_tool


def search(
    jql: str,
    max_results: int = 100,
    fields: Optional[List[str]] = None,
    detailed: bool = False,
) -> Dict[str, Any]:
    """Run a JQL query and return matching issues.

    Args:
        jql: A valid JQL query string, e.g.
            ``"project = PAY AND status = 'In Progress'"``.
        max_results: Safety cap on the number of issues returned.
        fields: Extra Jira fields to request in addition to the default set
            (e.g. a custom field ID discovered via ``list_fields``, like
            ``"customfield_10056"`` for a "Figma Link" field). Always
            included in the response's ``custom_fields`` regardless of
            ``detailed``.
        detailed: When ``False`` (default), each issue omits ``description``
            to keep bulk/list results token-cheap -- use this for scanning
            many issues (priority, status, blockers). Set ``True`` only when
            you actually need each issue's description text (e.g. inferring
            frontend/backend from a handful of issues); for a single issue,
            prefer ``issue_summary`` or ``get_issue`` instead of a detailed
            search.

    Returns:
        ``{"jql": "...", "count": N, "issues": [...]}``
    """

    def _run() -> Dict[str, Any]:
        query = require_str(jql, "jql")
        client = get_client()
        base_fields = DEFAULT_ISSUE_FIELDS if detailed else COMPACT_ISSUE_FIELDS
        requested_fields = list(base_fields) + list(fields or [])
        issues = client.search(query, max_results=max_results, fields=requested_fields)
        issue_dicts: List[Dict[str, Any]] = []
        for issue in issues:
            d = issue.to_dict()
            if not detailed:
                d.pop("description", None)
            d["blocked"] = is_issue_blocked(issue)
            issue_dicts.append(d)
        return {"jql": query, "count": len(issue_dicts), "issues": issue_dicts}

    return run_tool("search", _run)
