"""
Pytest fixtures and test configuration.

This module provides shared fixtures and test configuration
for the GitLab-Slack integration test suite.

Fixtures:
    mock_gitlab_project: Mocked GitLab project object.
    mock_gitlab_issue: Mocked GitLab issue object.
    mock_gitlab_client: Mocked GitLab API client.
    mock_slack_client: Mocked Slack WebClient.
    sample_issue_webhook_payload: Sample GitLab issue webhook payload.
    sample_issue_close_payload: Sample issue close event payload.
    sample_issue_update_payload: Sample issue update event payload.
"""

import os
from typing import Any, Generator
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
def mock_gitlab_project() -> MagicMock:
    """
    Create a mocked GitLab project object.

    Returns:
        MagicMock: Mock object representing a GitLab project.
    """
    project: MagicMock = MagicMock()
    return project


@pytest.fixture
def mock_gitlab_issue() -> MagicMock:
    """
    Create a mocked GitLab issue object with typical attributes.

    Returns:
        MagicMock: Mock object representing a GitLab issue with:
            - iid: 123
            - title: "Test Issue"
            - description: "Test description"
            - state: "opened"
            - labels: ["bug", "priority::high"]
            - web_url: Full URL to the issue
    """
    issue: MagicMock = MagicMock()
    issue.iid = 123
    issue.title = "Test Issue"
    issue.description = "Test description"
    issue.state = "opened"
    issue.labels = ["bug", "priority::high"]
    issue.web_url = "https://gitlab.test.com/project/issues/123"
    return issue


@pytest.fixture
def mock_gitlab_client(
    mock_gitlab_project: MagicMock,
    mock_gitlab_issue: MagicMock,
) -> Generator[MagicMock, None, None]:
    """
    Create a mocked GitLab client with project and issue operations.

    This fixture patches the global GitLab client used in the api module
    and configures it to return the mock project and issue objects.

    Args:
        mock_gitlab_project: Mocked project fixture.
        mock_gitlab_issue: Mocked issue fixture.

    Yields:
        MagicMock: Patched GitLab client with configured return values.
    """
    with patch("gitlab_slack.gitlab.api.gl") as mock_gl:
        mock_gl.projects.get.return_value = mock_gitlab_project
        mock_gitlab_project.issues.create.return_value = mock_gitlab_issue
        mock_gitlab_project.issues.get.return_value = mock_gitlab_issue
        mock_gitlab_project.issues.list.return_value = [mock_gitlab_issue]
        yield mock_gl


@pytest.fixture
def mock_slack_client() -> Generator[MagicMock, None, None]:
    """
    Create a mocked Slack WebClient.

    This fixture patches the Slack client used in the webhooks module
    for testing Slack message posting.

    Yields:
        MagicMock: Patched Slack WebClient with chat_postMessage configured.
    """
    with patch("gitlab_slack.gitlab.webhooks.slack_client") as mock_client:
        mock_client.chat_postMessage.return_value = {"ok": True}
        yield mock_client


@pytest.fixture
def sample_issue_webhook_payload() -> dict[str, Any]:
    """
    Create a sample GitLab issue webhook payload for open events.

    Returns:
        dict[str, Any]: Webhook payload matching GitLab's Issue Hook format
            with action="open" and state="opened".
    """
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
def sample_issue_close_payload(
    sample_issue_webhook_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a sample GitLab issue close webhook payload.

    Args:
        sample_issue_webhook_payload: Base payload to modify.

    Returns:
        dict[str, Any]: Webhook payload with action="close" and state="closed".
    """
    payload: dict[str, Any] = sample_issue_webhook_payload.copy()
    payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
    payload["object_attributes"]["action"] = "close"
    payload["object_attributes"]["state"] = "closed"
    return payload


@pytest.fixture
def sample_issue_update_payload(
    sample_issue_webhook_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a sample GitLab issue update webhook payload.

    Args:
        sample_issue_webhook_payload: Base payload to modify.

    Returns:
        dict[str, Any]: Webhook payload with action="update".
    """
    payload: dict[str, Any] = sample_issue_webhook_payload.copy()
    payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
    payload["object_attributes"]["action"] = "update"
    return payload
