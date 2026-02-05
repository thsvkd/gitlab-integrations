"""Pytest fixtures and configuration."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set test environment variables before importing app modules
os.environ.setdefault("GITLAB_URL", "https://gitlab.test.com")
os.environ.setdefault("GITLAB_TOKEN", "test-token")
os.environ.setdefault("GITLAB_PROJECT_ID", "1")
os.environ.setdefault("GITLAB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("SLACK_CHANNEL_ID", "C0123456789")


@pytest.fixture
def mock_gitlab_project():
    """Mock GitLab project object."""
    project = MagicMock()
    return project


@pytest.fixture
def mock_gitlab_issue():
    """Mock GitLab issue object."""
    issue = MagicMock()
    issue.iid = 123
    issue.title = "Test Issue"
    issue.description = "Test description"
    issue.state = "opened"
    issue.labels = ["bug", "priority::high"]
    issue.web_url = "https://gitlab.test.com/project/issues/123"
    return issue


@pytest.fixture
def mock_gitlab_client(mock_gitlab_project, mock_gitlab_issue):
    """Mock GitLab client."""
    with patch("gitlab_slack.gitlab.api.gl") as mock_gl:
        mock_gl.projects.get.return_value = mock_gitlab_project
        mock_gitlab_project.issues.create.return_value = mock_gitlab_issue
        mock_gitlab_project.issues.get.return_value = mock_gitlab_issue
        mock_gitlab_project.issues.list.return_value = [mock_gitlab_issue]
        yield mock_gl


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient."""
    with patch("gitlab_slack.gitlab.webhooks.slack_client") as mock_client:
        mock_client.chat_postMessage.return_value = {"ok": True}
        yield mock_client


@pytest.fixture
def sample_issue_webhook_payload():
    """Sample GitLab issue webhook payload."""
    return {
        "object_kind": "issue",
        "event_type": "issue",
        "user": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
            "email": "test@example.com",
        },
        "project": {
            "id": 1,
            "name": "Test Project",
            "web_url": "https://gitlab.test.com/test/project",
        },
        "object_attributes": {
            "id": 100,
            "iid": 123,
            "title": "Test Issue",
            "description": "This is a test issue description",
            "state": "opened",
            "action": "open",
            "url": "https://gitlab.test.com/test/project/issues/123",
        },
    }


@pytest.fixture
def sample_issue_close_payload(sample_issue_webhook_payload):
    """Sample GitLab issue close webhook payload."""
    payload = sample_issue_webhook_payload.copy()
    payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
    payload["object_attributes"]["action"] = "close"
    payload["object_attributes"]["state"] = "closed"
    return payload


@pytest.fixture
def sample_issue_update_payload(sample_issue_webhook_payload):
    """Sample GitLab issue update webhook payload."""
    payload = sample_issue_webhook_payload.copy()
    payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
    payload["object_attributes"]["action"] = "update"
    return payload
