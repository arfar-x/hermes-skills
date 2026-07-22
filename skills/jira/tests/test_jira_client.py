import pytest

from lib.jira_client import (
    JiraAuthError,
    JiraNotFoundError,
    JiraRateLimitError,
    JiraValidationError,
)
from tests.conftest import make_response


def test_search_empty_jql_rejected(client):
    with pytest.raises(JiraValidationError):
        client.search("")


def test_search_paginates_until_total_reached(client, mock_session):
    page1 = make_response(json_data={"issues": [{"key": "PAY-1", "fields": {}}], "total": 3})
    page2 = make_response(json_data={"issues": [{"key": "PAY-2", "fields": {}}], "total": 3})
    page3 = make_response(json_data={"issues": [{"key": "PAY-3", "fields": {}}], "total": 3})
    mock_session.request.side_effect = [page1, page2, page3]

    issues = client.search("project = PAY", max_results=None)

    assert [i.key for i in issues] == ["PAY-1", "PAY-2", "PAY-3"]
    assert mock_session.request.call_count == 3


def test_search_respects_max_results_cap(client, mock_session):
    page1 = make_response(json_data={"issues": [{"key": f"PAY-{i}", "fields": {}} for i in range(50)], "total": 200})
    mock_session.request.return_value = page1

    issues = client.search("project = PAY", max_results=10)

    assert len(issues) == 10


def test_get_issue_builds_typed_model(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "key": "PAY-1",
            "fields": {
                "summary": "Fix bug",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
                "updated": "2026-07-20T10:00:00Z",
                "created": "2026-07-01T10:00:00Z",
                "duedate": None,
                "labels": ["backend"],
                "issuelinks": [],
            },
        }
    )
    issue = client.get_issue("PAY-1")
    assert issue.key == "PAY-1"
    assert issue.summary == "Fix bug"
    assert issue.status == "In Progress"
    assert issue.priority == "High"
    assert issue.assignee == "Alice"
    assert issue.labels == ["backend"]


def test_get_issue_rejects_bad_key(client):
    with pytest.raises(JiraValidationError):
        client.get_issue("")
    with pytest.raises(JiraValidationError):
        client.get_issue("nokeyformat")


def test_401_raises_auth_error(client, mock_session):
    mock_session.request.return_value = make_response(status_code=401, json_data={"errorMessages": ["bad creds"]})
    with pytest.raises(JiraAuthError):
        client.get_issue("PAY-1")


def test_404_raises_not_found(client, mock_session):
    mock_session.request.return_value = make_response(status_code=404, json_data={"errorMessages": ["no such issue"]})
    with pytest.raises(JiraNotFoundError):
        client.get_issue("PAY-1")


def test_429_raises_rate_limit_error(client, mock_session):
    mock_session.request.return_value = make_response(
        status_code=429, json_data={"errorMessages": ["slow down"]}, headers={"Retry-After": "5"}
    )
    with pytest.raises(JiraRateLimitError):
        client.get_issue("PAY-1")


def test_add_worklog_builds_request_body(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "id": "1",
            "author": {"displayName": "Alice"},
            "timeSpent": "2h",
            "timeSpentSeconds": 7200,
            "comment": "did work",
            "started": "2026-07-21T10:00:00Z",
        }
    )
    worklog = client.add_worklog("PAY-1", 7200, "did work")
    assert worklog.time_spent_seconds == 7200

    _, kwargs = mock_session.request.call_args
    assert kwargs["json"] == {"timeSpentSeconds": 7200, "comment": "did work"}


def test_add_worklog_rejects_non_positive_duration(client):
    with pytest.raises(JiraValidationError):
        client.add_worklog("PAY-1", 0, "no time")


def test_get_transitions_builds_models(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "transitions": [
                {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Move to Review", "to": {"name": "Review"}},
            ]
        }
    )
    transitions = client.get_transitions("PAY-1")
    assert [t.name for t in transitions] == ["Start Progress", "Move to Review"]


def test_transition_issue_resolves_by_target_status_name(client, mock_session):
    transitions_response = make_response(
        json_data={
            "transitions": [
                {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Move to Review", "to": {"name": "Review"}},
            ]
        }
    )
    post_response = make_response(status_code=204)
    mock_session.request.side_effect = [transitions_response, post_response]

    result = client.transition_issue("PAY-1", "Review")

    assert result == {
        "issue_key": "PAY-1",
        "transitioned_to": "Review",
        "transition_name": "Move to Review",
        "success": True,
    }
    post_call_kwargs = mock_session.request.call_args_list[1].kwargs
    assert post_call_kwargs["json"] == {"transition": {"id": "21"}}


def test_transition_issue_unmatched_raises_with_options(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={"transitions": [{"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}}]}
    )
    with pytest.raises(JiraValidationError, match="Start Progress"):
        client.transition_issue("PAY-1", "Nonexistent Status")


def test_search_users_handles_list_payload(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data=[{"accountId": "1", "displayName": "Alice", "emailAddress": "a@example.com", "active": True}]
    )
    users = client.search_users("alice")
    assert users[0].display_name == "Alice"


def test_search_users_rejects_empty_query(client):
    with pytest.raises(JiraValidationError):
        client.search_users("")
