"""kanban_status: column breakdown for a kanban board.

Thin tool: delegates entirely to the shared JiraClient's agile endpoints.
Kanban boards have no sprints (see sprint()'s "note" when it detects one) --
this is the equivalent "what's the state of the board" answer for them.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from lib.jira_client import JiraNotFoundError, get_client
from tools._common import run_tool


def kanban_status(board_id: Optional[int] = None, project: Optional[str] = None) -> Dict[str, Any]:
    """Return a kanban board's columns and per-column issue counts.

    Args:
        board_id: Optional explicit board id. When omitted, a board is
            resolved for ``project`` (falls back to ``JIRA_DEFAULT_PROJECT``).
        project: Project key to resolve a board for, when ``board_id``
            isn't given.

    Returns:
        ``{"board_id": ..., "columns": [...], "issue_counts_by_column": {...}}``
    """

    def _run() -> Dict[str, Any]:
        client = get_client()
        resolved_board_id = board_id
        if resolved_board_id is None:
            board = client.current_board(project=project)
            if board is None:
                resolved_project = client.resolve_project(project)
                scope = f"project {resolved_project}" if resolved_project else "any project (instance-wide)"
                raise JiraNotFoundError(f"No board found for {scope}.")
            resolved_board_id = board.id
        return client.kanban_status(resolved_board_id)

    return run_tool("kanban_status", _run)
