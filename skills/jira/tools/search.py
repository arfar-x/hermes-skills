"""search: run an arbitrary JQL query and return structured issue data.

Thin tool: validates the JQL is non-empty, delegates to the shared
JiraClient, and returns issue JSON. Query construction/interpretation is
the LLM's responsibility; this tool never rewrites or infers JQL.
"""

from __future__ import annotations

from typing import Any, Dict, List

from lib.jira_client import get_client
from lib.utils import is_issue_blocked
from tools._common import require_str, run_tool


def search(jql: str, max_results: int = 100) -> Dict[str, Any]:
    """Run a JQL query and return matching issues.

    Args:
        jql: A valid JQL query string, e.g.
            ``"project = PAY AND status = 'In Progress'"``.
        max_results: Safety cap on the number of issues returned.

    Returns:
        ``{"jql": "...", "count": N, "issues": [...]}``
    """

    def _run() -> Dict[str, Any]:
        query = require_str(jql, "jql")
        client = get_client()
        issues = client.search(query, max_results=max_results)
        issue_dicts: List[Dict[str, Any]] = []
        for issue in issues:
            d = issue.to_dict()
            d["blocked"] = is_issue_blocked(issue)
            issue_dicts.append(d)
        return {"jql": query, "count": len(issue_dicts), "issues": issue_dicts}

    return run_tool("search", _run)
