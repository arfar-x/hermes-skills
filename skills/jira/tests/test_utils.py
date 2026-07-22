import pytest

from lib.models import Issue, IssueLink
from lib.utils import (
    InvalidDurationError,
    adf_to_plain_text,
    blocking_reasons,
    is_issue_blocked,
    parse_duration_to_seconds,
    safe_get,
)


@pytest.mark.parametrize(
    "duration, expected_seconds",
    [
        ("2h", 2 * 3600),
        ("30m", 30 * 60),
        ("1d", 8 * 3600),
        ("1w", 5 * 8 * 3600),
        ("1d 4h", 8 * 3600 + 4 * 3600),
        ("1h 30m", 3600 + 30 * 60),
    ],
)
def test_parse_duration_to_seconds(duration, expected_seconds):
    assert parse_duration_to_seconds(duration) == expected_seconds


@pytest.mark.parametrize("bad_duration", ["", "   ", "abc", "2x", "0h"])
def test_parse_duration_rejects_invalid(bad_duration):
    with pytest.raises(InvalidDurationError):
        parse_duration_to_seconds(bad_duration)


def test_adf_to_plain_text_extracts_text_nodes():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world"}]}
        ],
    }
    assert "Hello" in adf_to_plain_text(adf)
    assert "world" in adf_to_plain_text(adf)


def test_adf_to_plain_text_passthrough_for_plain_string():
    assert adf_to_plain_text("already plain") == "already plain"


def test_safe_get_walks_nested_dicts():
    data = {"a": {"b": {"c": 42}}}
    assert safe_get(data, "a", "b", "c") == 42
    assert safe_get(data, "a", "x", default="missing") == "missing"
    assert safe_get(None, "a", default="missing") == "missing"


def _issue(status="To Do", links=None):
    return Issue(
        key="PAY-1",
        summary="s",
        status=status,
        priority="High",
        issue_type="Task",
        assignee="Alice",
        reporter="Bob",
        updated=None,
        created=None,
        due_date=None,
        links=links or [],
    )


def test_blocking_reasons_status_flag():
    issue = _issue(status="Blocked")
    reasons = blocking_reasons(issue)
    assert any("Status is 'Blocked'" in r for r in reasons)
    assert is_issue_blocked(issue) is True


def test_blocking_reasons_open_blocking_link():
    link = IssueLink(
        link_type="is blocked by",
        direction="inward",
        related_key="PAY-2",
        related_summary="dependency",
        related_status="In Progress",
    )
    issue = _issue(status="To Do", links=[link])
    reasons = blocking_reasons(issue)
    assert reasons == ["Blocked by PAY-2 (status: In Progress)"]
    assert is_issue_blocked(issue) is True


def test_blocking_reasons_resolved_blocking_link_not_blocked():
    link = IssueLink(
        link_type="is blocked by",
        direction="inward",
        related_key="PAY-2",
        related_summary="dependency",
        related_status="Done",
    )
    issue = _issue(status="To Do", links=[link])
    assert blocking_reasons(issue) == []
    assert is_issue_blocked(issue) is False


def test_blocking_reasons_unrelated_link_ignored():
    link = IssueLink(
        link_type="relates to",
        direction="outward",
        related_key="PAY-3",
        related_summary="other",
        related_status="Done",
    )
    issue = _issue(status="To Do", links=[link])
    assert blocking_reasons(issue) == []
