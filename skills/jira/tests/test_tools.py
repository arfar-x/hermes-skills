from unittest.mock import MagicMock, patch

from lib.auth import JiraConfig
from lib.models import Comment, Issue, IssueLink, Sprint, Worklog
from tools import blockers, issue_summary, my_work, search, sprint, transition, worklog


def _issue(key="PAY-1", status="To Do", links=None, priority="High", updated="2026-07-20"):
    return Issue(
        key=key,
        summary="Fix bug",
        status=status,
        priority=priority,
        issue_type="Bug",
        assignee="Alice",
        reporter="Bob",
        updated=updated,
        created="2026-07-01",
        due_date=None,
        links=links or [],
    )


def _fake_config(auto_confirm=False):
    return JiraConfig(
        base_url="https://jira.example.com",
        username="alice",
        password="secret",
        auto_confirm_writes=auto_confirm,
    )


def test_my_work_returns_list_with_blocked_flag():
    mock_client = MagicMock()
    mock_client.search.return_value = [_issue(status="Blocked")]
    with patch("tools.my_work.get_client", return_value=mock_client):
        result = my_work.my_work()
    assert result[0]["key"] == "PAY-1"
    assert result[0]["blocked"] is True
    mock_client.search.assert_called_once()


def test_my_work_wraps_errors_as_json():
    mock_client = MagicMock()
    from lib.jira_client import JiraApiError

    mock_client.search.side_effect = JiraApiError("boom", status_code=500)
    with patch("tools.my_work.get_client", return_value=mock_client):
        result = my_work.my_work()
    assert "error" in result


def test_blockers_reports_reasons():
    link = IssueLink("is blocked by", "inward", "PAY-2", "dep", "In Progress")
    mock_client = MagicMock()
    mock_client.get_issue.return_value = _issue(links=[link])
    mock_client.get_comments.return_value = []
    with patch("tools.blockers.get_client", return_value=mock_client):
        result = blockers.blockers("PAY-1")
    assert result["blocked"] is True
    assert "PAY-2" in result["reasons"][0]


def test_blockers_rejects_empty_issue_key():
    result = blockers.blockers("")
    assert result["error"]["type"] == "invalid_input"


def test_issue_summary_combines_all_sources():
    mock_client = MagicMock()
    mock_client.get_issue.return_value = _issue()
    mock_client.get_comments.return_value = [Comment("1", "Alice", "hi", "2026-07-01", None)]
    mock_client.get_worklogs.return_value = [Worklog("1", "Alice", "2h", 7200, "work", "2026-07-01")]
    mock_client.get_changelog.return_value = []
    with patch("tools.issue_summary.get_client", return_value=mock_client):
        result = issue_summary.issue_summary("PAY-1")
    assert result["issue"]["key"] == "PAY-1"
    assert len(result["comments"]) == 1
    assert len(result["worklogs"]) == 1


def test_search_requires_jql():
    result = search.search("")
    assert result["error"]["type"] == "invalid_input"


def test_search_returns_count_and_issues():
    mock_client = MagicMock()
    mock_client.search.return_value = [_issue()]
    with patch("tools.search.get_client", return_value=mock_client):
        result = search.search("project = PAY")
    assert result["count"] == 1
    assert result["issues"][0]["key"] == "PAY-1"


def test_worklog_requires_confirmation_by_default():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work")
    assert result["confirmed"] is False
    assert result["requires_confirmation"] is True
    mock_client.add_worklog.assert_not_called()


def test_worklog_executes_when_confirmed():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    mock_client.add_worklog.return_value = Worklog("1", "Alice", "2h", 7200, "did work", "2026-07-21")
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work", confirm=True)
    assert result["confirmed"] is True
    mock_client.add_worklog.assert_called_once_with("PAY-1", 7200, "did work")


def test_worklog_auto_confirm_config_skips_gate():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    mock_client.add_worklog.return_value = Worklog("1", "Alice", "2h", 7200, "did work", "2026-07-21")
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work")
    assert result["confirmed"] is True


def test_worklog_rejects_bad_duration():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "not-a-duration", "did work")
    assert result["error"]["type"] == "invalid_input"


def test_transition_requires_confirmation_by_default():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.transition.get_client", return_value=mock_client):
        result = transition.transition("PAY-1", "Review")
    assert result["requires_confirmation"] is True
    mock_client.transition_issue.assert_not_called()


def test_transition_executes_when_confirmed():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    mock_client.transition_issue.return_value = {
        "issue_key": "PAY-1",
        "transitioned_to": "Review",
        "transition_name": "Move to Review",
        "success": True,
    }
    with patch("tools.transition.get_client", return_value=mock_client):
        result = transition.transition("PAY-1", "Review", confirm=True)
    assert result["confirmed"] is True
    assert result["transitioned_to"] == "Review"


def test_sprint_returns_board_and_active_sprint():
    mock_client = MagicMock()
    from lib.models import Board

    mock_client.current_board.return_value = Board(3, "PAY Board", "scrum")
    mock_client.current_sprint.return_value = Sprint(55, "Sprint 12", "active", "2026-07-01", "2026-07-15", "Ship it", 3)
    with patch("tools.sprint.get_client", return_value=mock_client):
        result = sprint.sprint()
    assert result["board"]["name"] == "PAY Board"
    assert result["sprint"]["goal"] == "Ship it"
