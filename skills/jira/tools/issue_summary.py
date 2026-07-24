"""issue_summary: retrieve everything about an issue as one JSON document.

Thin tool: fans out to the shared JiraClient for the issue, comments,
worklogs, changelog, and linked issues, and returns them combined. No
prose summarization happens here -- the LLM produces the human summary
from this JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import get_client
from tools._common import ToolInputError, require_str, run_tool

_VALID_SECTIONS = {"issue", "comments", "worklogs", "changelog", "linked_issues"}


def issue_summary(issue_key: str, sections: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return a single JSON document combining an issue's full context.

    Args:
        issue_key: Issue key, e.g. ``PAY-412``.
        sections: Which parts to fetch and return, a subset of
            ``{"issue", "comments", "worklogs", "changelog", "linked_issues"}``.
            Defaults to all -- pass a subset (e.g. ``["issue"]``) to skip
            fetching and returning the rest, when you only need current
            fields rather than the full history.

    Returns:
        ``{"issue": {...}, "comments": [...], "worklogs": [...],
           "changelog": [...], "linked_issues": [...]}``, containing only
        the requested ``sections``.
    """

    def _run() -> Dict[str, Any]:
        key = require_str(issue_key, "issue_key")
        wanted = set(sections) if sections is not None else set(_VALID_SECTIONS)
        unknown = wanted - _VALID_SECTIONS
        if unknown:
            raise ToolInputError(
                f"Unknown section(s) {sorted(unknown)}. Valid sections: {sorted(_VALID_SECTIONS)}."
            )

        client = get_client()
        # Fetched even if "issue" wasn't requested -- "linked_issues" is
        # derived from it, and the fetch is cheap (a single call either way).
        issue = client.get_issue(key)

        result: Dict[str, Any] = {}
        if "issue" in wanted:
            result["issue"] = issue.to_dict()
        if "comments" in wanted:
            result["comments"] = [c.to_dict() for c in client.get_comments(key)]
        if "worklogs" in wanted:
            result["worklogs"] = [w.to_dict() for w in client.get_worklogs(key)]
        if "changelog" in wanted:
            result["changelog"] = [c.to_dict() for c in client.get_changelog(key)]
        if "linked_issues" in wanted:
            result["linked_issues"] = [link.to_dict() for link in issue.links]
        return result

    return run_tool("issue_summary", _run)
