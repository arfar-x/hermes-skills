"""search_users: look up Jira users by name/email fragment.

Thin tool: delegates to the shared JiraClient. Exists so the LLM can
resolve a person's name (e.g. "John") to an ``account_id`` for use in
JQL (``assignee = accountId(...)``) or for supplying an ``assignee``
value to ``create_issue``/``edit_issue`` -- without writing its own
request to Jira's user-search endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import get_client
from tools._common import require_str, run_tool


def search_users(
    query: str,
    project: Optional[str] = None,
    all_projects: bool = False,
    max_results: int = 25,
) -> Dict[str, Any]:
    """Search for users by name/email fragment.

    Args:
        query: Name, username, or email fragment, e.g. ``"john"``.
        project: Scope the search to users assignable in this project
            instead of every user on the instance -- narrower, and
            disambiguates common names that only collide instance-wide
            (e.g. two people named "Sam", only one of them on this
            project's board). Falls back to ``JIRA_DEFAULT_PROJECT`` if
            set, then to an unscoped search if neither is available.
        all_projects: Force an unscoped, instance-wide search, ignoring
            both ``project`` and ``JIRA_DEFAULT_PROJECT``. Use this to
            retry broader after a scoped search returns no match --
            omitting ``project`` alone won't do that if
            ``JIRA_DEFAULT_PROJECT`` is set, since it would still apply.
        max_results: Safety cap on the number of users returned.

    Returns:
        ``{"query": "...", "project": "PAY" | null, "count": N,
           "users": [{"account_id", "display_name", "email", "active"}, ...]}``.
        ``project`` is the scope actually used (``null`` if unscoped) --
        use it to tell whether a "no match"/ambiguous result came from a
        scoped or instance-wide search.

        - `count: 0` and `project` is set: don't conclude there's no such
          user -- ask whether to broaden to an instance-wide search
          (retry with `all_projects=true`) before telling the user no
          match was found.
        - `count: 0` and `project` is null: no match anywhere; tell the
          user, don't guess a name variant.
        - `count: 1`: use `users[0].account_id`.
        - `count > 1`: if `project` is null and a project is known/relevant,
          retry scoped first -- it may resolve on its own. Otherwise ask
          the user which person they meant (show `display_name`/`email`
          for each) rather than picking the first result.
    """

    def _run() -> Dict[str, Any]:
        q = require_str(query, "query")
        client = get_client()
        resolved_project = None if all_projects else client.resolve_project(project)
        users: List[Any] = client.search_users(
            q, project=project, all_projects=all_projects, max_results=max_results
        )
        user_dicts = [u.to_dict() for u in users]
        return {
            "query": q,
            "project": resolved_project,
            "count": len(user_dicts),
            "users": user_dicts,
        }

    return run_tool("search_users", _run)
