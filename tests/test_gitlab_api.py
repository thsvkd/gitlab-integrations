"""Tests for GitLab API client."""

from unittest.mock import MagicMock, patch

import gitlab
import pytest


class TestCreateIssue:
    """Tests for create_issue function."""

    def test_create_issue_success(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test successful issue creation."""
        from gitlab_integrations.gitlab.api import create_issue

        result = create_issue(title="Test Issue", description="Test description")

        mock_gitlab_project.issues.create.assert_called_once_with({
            "title": "Test Issue",
            "description": "Test description",
            "labels": [],
        })
        assert result.iid == 123
        assert result.title == "Test Issue"

    def test_create_issue_with_labels(self, mock_gitlab_client, mock_gitlab_project):
        """Test issue creation with labels."""
        from gitlab_integrations.gitlab.api import create_issue

        labels = ["bug", "priority::high"]
        create_issue(title="Bug Report", description="Found a bug", labels=labels)

        mock_gitlab_project.issues.create.assert_called_once_with({
            "title": "Bug Report",
            "description": "Found a bug",
            "labels": labels,
        })

    def test_create_issue_empty_description(self, mock_gitlab_client, mock_gitlab_project):
        """Test issue creation with empty description."""
        from gitlab_integrations.gitlab.api import create_issue

        create_issue(title="Title Only")

        mock_gitlab_project.issues.create.assert_called_once_with({
            "title": "Title Only",
            "description": "",
            "labels": [],
        })


class TestGetIssueByIid:
    """Tests for get_issue_by_iid function."""

    def test_get_issue_found(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test successful issue retrieval."""
        from gitlab_integrations.gitlab.api import get_issue_by_iid

        result = get_issue_by_iid(123)

        mock_gitlab_project.issues.get.assert_called_once_with(123)
        assert result.iid == 123
        assert result.title == "Test Issue"

    def test_get_issue_not_found(self, mock_gitlab_client, mock_gitlab_project):
        """Test issue not found returns None."""
        from gitlab_integrations.gitlab.api import get_issue_by_iid

        mock_gitlab_project.issues.get.side_effect = gitlab.exceptions.GitlabGetError(
            response_code=404, error_message="Not found"
        )

        result = get_issue_by_iid(999)

        assert result is None


class TestUpdateIssueState:
    """Tests for update_issue_state function."""

    def test_close_issue(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test closing an issue."""
        from gitlab_integrations.gitlab.api import update_issue_state

        result = update_issue_state(123, "close")

        mock_gitlab_project.issues.get.assert_called_once_with(123)
        assert mock_gitlab_issue.state_event == "close"
        mock_gitlab_issue.save.assert_called_once()

    def test_reopen_issue(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test reopening an issue."""
        from gitlab_integrations.gitlab.api import update_issue_state

        result = update_issue_state(123, "reopen")

        assert mock_gitlab_issue.state_event == "reopen"
        mock_gitlab_issue.save.assert_called_once()


class TestListIssues:
    """Tests for list_issues function."""

    def test_list_opened_issues(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test listing opened issues."""
        from gitlab_integrations.gitlab.api import list_issues

        result = list_issues(state="opened")

        mock_gitlab_project.issues.list.assert_called_once_with(state="opened", per_page=10)
        assert len(result) == 1
        assert result[0].iid == 123

    def test_list_issues_custom_per_page(self, mock_gitlab_client, mock_gitlab_project):
        """Test listing issues with custom per_page."""
        from gitlab_integrations.gitlab.api import list_issues

        list_issues(state="all", per_page=50)

        mock_gitlab_project.issues.list.assert_called_once_with(state="all", per_page=50)
