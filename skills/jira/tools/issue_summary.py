"""issue_summary: retrieve everything about an issue as one JSON document.

Thin tool: fans out to the shared JiraClient for the issue, comments,
worklogs, changelog, and linked issues, and returns them combined. No
prose summarization happens here -- the LLM produces the human summary
from this JSON.
"""

from __future__ import annotations

from typing import Any, Dict

from lib.jira_client import get_client
from tools._common import require_str, run_tool


def issue_summary(issue_key: str) -> Dict[str, Any]:
    """Return a single JSON document combining an issue's full context.

    Args:
        issue_key: Issue key, e.g. ``PAY-412``.

    Returns:
        ``{"issue": {...}, "comments": [...], "worklogs": [...],
           "changelog": [...], "linked_issues": [...]}``
    """

    def _run() -> Dict[str, Any]:
        key = require_str(issue_key, "issue_key")
        client = get_client()
        issue = client.get_issue(key)
        comments = client.get_comments(key)
        worklogs = client.get_worklogs(key)
        changelog = client.get_changelog(key)

        return {
            "issue": issue.to_dict(),
            "comments": [c.to_dict() for c in comments],
            "worklogs": [w.to_dict() for w in worklogs],
            "changelog": [c.to_dict() for c in changelog],
            "linked_issues": [link.to_dict() for link in issue.links],
        }

    return run_tool("issue_summary", _run)
