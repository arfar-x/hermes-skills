"""search_users: look up Jira users by name/email fragment.

Thin tool: delegates to the shared JiraClient. Exists so the LLM can
resolve a person's name (e.g. "John") to an ``account_id`` for use in
JQL (``assignee = accountId(...)``) or for supplying an ``assignee``
value to ``create_issue``/``edit_issue`` -- without writing its own
request to Jira's user-search endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List

from lib.jira_client import get_client
from tools._common import require_str, run_tool


def search_users(query: str, max_results: int = 25) -> Dict[str, Any]:
    """Search for users by name/email fragment.

    Args:
        query: Name, username, or email fragment, e.g. ``"john"``.
        max_results: Safety cap on the number of users returned.

    Returns:
        ``{"query": "...", "count": N, "users": [{"account_id", "display_name",
           "email", "active"}, ...]}``. If ``count`` is 0, tell the user no
        match was found rather than guessing an account_id. If more than
        one user matches, ask the user which one they meant rather than
        picking the first result.
    """

    def _run() -> Dict[str, Any]:
        q = require_str(query, "query")
        client = get_client()
        users: List[Any] = client.search_users(q, max_results=max_results)
        user_dicts = [u.to_dict() for u in users]
        return {"query": q, "count": len(user_dicts), "users": user_dicts}

    return run_tool("search_users", _run)
