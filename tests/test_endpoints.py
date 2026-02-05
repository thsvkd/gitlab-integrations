"""Tests for FastAPI endpoints."""

import sys
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    """Create test client with mocked Slack app."""
    # Mock slack_bolt.App before importing main
    mock_app_instance = MagicMock()
    mock_app_class = MagicMock(return_value=mock_app_instance)
    mock_handler_instance = MagicMock()
    mock_handler_class = MagicMock(return_value=mock_handler_instance)

    # Mock the async handle method
    async def mock_handle(request):
        return {"ok": True}
    mock_handler_instance.handle = mock_handle

    with patch.dict(sys.modules, {}):
        with patch("slack_bolt.App", mock_app_class):
            with patch("slack_bolt.adapter.fastapi.SlackRequestHandler", mock_handler_class):
                # Remove cached modules to force re-import
                modules_to_remove = [
                    key for key in sys.modules.keys()
                    if key.startswith("gitlab_slack")
                ]
                for mod in modules_to_remove:
                    sys.modules.pop(mod, None)

                from gitlab_slack.main import app
                from fastapi.testclient import TestClient
                yield TestClient(app)

                # Clean up modules after test
                for mod in list(sys.modules.keys()):
                    if mod.startswith("gitlab_slack"):
                        sys.modules.pop(mod, None)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns 200 with correct response."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gitlab-slack-integration"


class TestGitLabWebhookEndpoint:
    """Tests for GitLab webhook endpoint."""

    def test_webhook_without_event_header(self, client):
        """Test webhook returns 400 without X-Gitlab-Event header."""
        response = client.post(
            "/gitlab/webhook",
            json={"test": "data"},
        )

        assert response.status_code == 400

    def test_webhook_with_invalid_secret(self, client):
        """Test webhook returns 401 with invalid secret."""
        response = client.post(
            "/gitlab/webhook",
            json={"object_attributes": {"action": "open"}},
            headers={
                "X-Gitlab-Event": "Issue Hook",
                "X-Gitlab-Token": "invalid-secret",
            },
        )

        assert response.status_code == 401

    def test_webhook_with_valid_secret(self, client):
        """Test webhook returns 200 with valid secret."""
        with patch("gitlab_slack.gitlab.webhooks.slack_client") as mock_client:
            mock_client.chat_postMessage.return_value = {"ok": True}

            response = client.post(
                "/gitlab/webhook",
                json={
                    "object_attributes": {
                        "action": "open",
                        "iid": 123,
                        "title": "Test",
                        "url": "https://test.com",
                        "state": "opened",
                        "description": "Test desc",
                    },
                    "user": {"name": "Test User"},
                },
                headers={
                    "X-Gitlab-Event": "Issue Hook",
                    "X-Gitlab-Token": "test-webhook-secret",
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_webhook_unsupported_event(self, client):
        """Test webhook ignores unsupported events."""
        response = client.post(
            "/gitlab/webhook",
            json={"test": "data"},
            headers={
                "X-Gitlab-Event": "Push Hook",
                "X-Gitlab-Token": "test-webhook-secret",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSlackEndpoints:
    """Tests for Slack endpoints."""

    def test_slack_commands_endpoint_exists(self, client):
        """Test that /slack/commands endpoint exists."""
        response = client.post(
            "/slack/commands",
            data={"command": "/issue", "text": ""},
        )

        # Endpoint exists (not 404) and mocked handler returns success
        assert response.status_code != 404

    def test_slack_interactions_endpoint_exists(self, client):
        """Test that /slack/interactions endpoint exists."""
        response = client.post(
            "/slack/interactions",
            data={"payload": "{}"},
        )

        assert response.status_code != 404

    def test_slack_events_endpoint_exists(self, client):
        """Test that /slack/events endpoint exists."""
        response = client.post(
            "/slack/events",
            json={"type": "url_verification", "challenge": "test"},
        )

        assert response.status_code != 404
