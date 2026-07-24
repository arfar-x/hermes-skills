"""Typed data models returned by the Jira client.

These are intentionally plain, JSON-serializable dataclasses. Tools return
``to_dict()`` output directly -- the LLM never sees Jira's raw REST
payloads, only these normalized structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class User:
    account_id: Optional[str]
    display_name: Optional[str]
    email: Optional[str] = None
    active: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "display_name": self.display_name,
            "email": self.email,
            "active": self.active,
        }


@dataclass(frozen=True)
class IssueLink:
    link_type: str
    direction: str  # "inward" or "outward"
    related_key: str
    related_summary: Optional[str]
    related_status: Optional[str]
    related_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.link_type,
            "direction": self.direction,
            "related_key": self.related_key,
            "related_summary": self.related_summary,
            "related_status": self.related_status,
            "related_url": self.related_url,
        }


@dataclass(frozen=True)
class Comment:
    id: str
    author: Optional[str]
    body: str
    created: Optional[str]
    updated: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author,
            "body": self.body,
            "created": self.created,
            "updated": self.updated,
        }


@dataclass(frozen=True)
class Worklog:
    id: str
    author: Optional[str]
    time_spent: str
    time_spent_seconds: int
    comment: Optional[str]
    started: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author,
            "time_spent": self.time_spent,
            "time_spent_seconds": self.time_spent_seconds,
            "comment": self.comment,
            "started": self.started,
        }


@dataclass(frozen=True)
class ChangelogEntry:
    id: str
    author: Optional[str]
    created: Optional[str]
    field: str
    from_value: Optional[str]
    to_value: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author,
            "created": self.created,
            "field": self.field,
            "from": self.from_value,
            "to": self.to_value,
        }


@dataclass(frozen=True)
class Transition:
    id: str
    name: str
    to_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "to_status": self.to_status}


@dataclass(frozen=True)
class Issue:
    key: str
    summary: str
    status: str
    priority: Optional[str]
    issue_type: Optional[str]
    assignee: Optional[str]
    reporter: Optional[str]
    updated: Optional[str]
    created: Optional[str]
    due_date: Optional[str]
    labels: List[str] = field(default_factory=list)
    links: List[IssueLink] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    original_estimate_seconds: Optional[int] = None
    time_spent_seconds: Optional[int] = None
    remaining_estimate_seconds: Optional[int] = None
    description: Optional[str] = None
    components: List[str] = field(default_factory=list)
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None

    def to_dict(self, only: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """Serialize this issue.

        Args:
            only: When given, keep only these keys (plus "key", "url", and
                "custom_fields", which are always present) -- used by tools
                like ``search()`` to return exactly the fields a caller
                asked for instead of every field, e.g. via
                ``lib.jira_client.resolve_issue_fields()``. ``None`` (the
                default) returns every field, unchanged from before this
                parameter existed.
        """
        full = {
            "key": self.key,
            "url": self.url,
            "summary": self.summary,
            "status": self.status,
            "priority": self.priority,
            "issue_type": self.issue_type,
            "assignee": self.assignee,
            "reporter": self.reporter,
            "updated": self.updated,
            "created": self.created,
            "due_date": self.due_date,
            "labels": self.labels,
            "links": [link.to_dict() for link in self.links],
            "original_estimate_seconds": self.original_estimate_seconds,
            "time_spent_seconds": self.time_spent_seconds,
            "remaining_estimate_seconds": self.remaining_estimate_seconds,
            "description": self.description,
            "components": self.components,
            "subtasks": self.subtasks,
            "custom_fields": self.custom_fields,
        }
        if only is None:
            return full
        keep = set(only) | {"key", "url", "custom_fields"}
        return {k: v for k, v in full.items() if k in keep}


@dataclass(frozen=True)
class Sprint:
    id: int
    name: str
    state: str
    start_date: Optional[str]
    end_date: Optional[str]
    goal: Optional[str]
    board_id: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "goal": self.goal,
            "board_id": self.board_id,
        }


@dataclass(frozen=True)
class Board:
    id: int
    name: str
    type: str

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "type": self.type}
