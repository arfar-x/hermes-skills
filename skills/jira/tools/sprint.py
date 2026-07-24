"""sprint: report the active sprint, its board, dates, and goal.

Thin tool: delegates entirely to the shared JiraClient's agile endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from lib.jira_client import get_client
from tools._common import run_tool


def sprint(board_id: Optional[int] = None, project: Optional[str] = None) -> Dict[str, Any]:
    """Return the active sprint for a board.

    Args:
        board_id: Optional explicit board id. When omitted, a board is
            resolved for ``project`` (see below).
        project: Project key to resolve a board for. Falls back to
            ``JIRA_DEFAULT_PROJECT`` if unset; if neither resolves, the
            first board visible to the authenticated user instance-wide
            is used instead.

    Returns:
        ``{"board": {...}, "sprint": {...} | null}`` normally. If the
        resolved board is a kanban board (no sprints), ``"sprint"`` is
        ``null`` and a ``"note"`` explains it and points at
        ``kanban_status`` instead. If no board is found at all,
        ``"board"`` and ``"sprint"`` are both ``null`` with a ``"note"``
        naming the project that was searched.
    """

    def _run() -> Dict[str, Any]:
        client = get_client()

        if board_id is not None:
            active_sprint = client.current_sprint(board_id)
            return {
                "board": {"id": board_id},
                "sprint": active_sprint.to_dict() if active_sprint else None,
            }

        board = client.current_board(project=project)
        if board is None:
            resolved_project = client.resolve_project(project)
            scope = f"project {resolved_project}" if resolved_project else "any project (instance-wide)"
            return {
                "board": None,
                "sprint": None,
                "note": f"No board found for {scope}.",
            }

        if board.type == "kanban":
            return {
                "board": board.to_dict(),
                "sprint": None,
                "note": (
                    "This is a kanban board -- kanban boards don't run sprints, so there is "
                    "no 'active sprint' to report. Use kanban_status for its column/status "
                    "breakdown instead."
                ),
            }

        active_sprint = client.current_sprint(board.id)
        return {
            "board": board.to_dict(),
            "sprint": active_sprint.to_dict() if active_sprint else None,
        }

    return run_tool("sprint", _run)
