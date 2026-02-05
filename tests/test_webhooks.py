"""Tests for GitLab Webhook handlers."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


class TestWebhookSecretValidation:
    """Tests for webhook secret validation."""

    @pytest.mark.asyncio
    async def test_missing_event_header(self):
        """Test that missing X-Gitlab-Event header returns 400."""
        from unittest.mock import MagicMock
        from gitlab_integrations.gitlab.webhooks import handle_gitlab_webhook

        request = MagicMock()
        request.json = AsyncMock(return_value={})

        with pytest.raises(HTTPException) as exc_info:
            await handle_gitlab_webhook(
                request=request,
                x_gitlab_event=None,
                x_gitlab_token=None,
            )

        assert exc_info.value.status_code == 400
        assert "Missing X-Gitlab-Event header" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_webhook_secret(self):
        """Test that invalid webhook secret returns 401."""
        from unittest.mock import MagicMock
        from gitlab_integrations.gitlab.webhooks import handle_gitlab_webhook

        request = MagicMock()
        request.json = AsyncMock(return_value={})

        with pytest.raises(HTTPException) as exc_info:
            await handle_gitlab_webhook(
                request=request,
                x_gitlab_event="Issue Hook",
                x_gitlab_token="wrong-secret",
            )

        assert exc_info.value.status_code == 401
        assert "Invalid webhook token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_webhook_secret(self, mock_slack_client, sample_issue_webhook_payload):
        """Test that valid webhook secret is accepted."""
        from unittest.mock import MagicMock
        from gitlab_integrations.gitlab.webhooks import handle_gitlab_webhook

        request = MagicMock()
        request.json = AsyncMock(return_value=sample_issue_webhook_payload)

        result = await handle_gitlab_webhook(
            request=request,
            x_gitlab_event="Issue Hook",
            x_gitlab_token="test-webhook-secret",
        )

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_no_secret_configured(self, sample_issue_webhook_payload):
        """Test that webhook works when no secret is configured."""
        from unittest.mock import MagicMock
        from gitlab_integrations.gitlab import webhooks
        from gitlab_integrations.config import settings

        request = MagicMock()
        request.json = AsyncMock(return_value=sample_issue_webhook_payload)

        # Temporarily disable secret
        original_secret = settings.gitlab_webhook_secret
        with patch.object(settings, 'gitlab_webhook_secret', None):
            with patch.object(webhooks, 'slack_client') as mock_client:
                mock_client.chat_postMessage.return_value = {"ok": True}
                result = await webhooks.handle_gitlab_webhook(
                    request=request,
                    x_gitlab_event="Issue Hook",
                    x_gitlab_token=None,
                )

        assert result == {"status": "ok"}


class TestHandleIssueEvent:
    """Tests for issue event handling."""

    @pytest.mark.asyncio
    async def test_handle_issue_open_event(self, mock_slack_client, sample_issue_webhook_payload):
        """Test handling issue open event."""
        from gitlab_integrations.gitlab.webhooks import handle_issue_event

        await handle_issue_event(sample_issue_webhook_payload)

        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        assert "New issue created" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_issue_close_event(self, mock_slack_client, sample_issue_close_payload):
        """Test handling issue close event."""
        from gitlab_integrations.gitlab.webhooks import handle_issue_event

        await handle_issue_event(sample_issue_close_payload)

        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        assert "Issue closed" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_issue_update_event(self, mock_slack_client, sample_issue_update_payload):
        """Test handling issue update event."""
        from gitlab_integrations.gitlab.webhooks import handle_issue_event

        await handle_issue_event(sample_issue_update_payload)

        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        assert "Issue updated" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_issue_reopen_event(self, mock_slack_client, sample_issue_webhook_payload):
        """Test handling issue reopen event."""
        from gitlab_integrations.gitlab.webhooks import handle_issue_event

        payload = sample_issue_webhook_payload.copy()
        payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
        payload["object_attributes"]["action"] = "reopen"

        await handle_issue_event(payload)

        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        assert "Issue reopened" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self, mock_slack_client, sample_issue_webhook_payload):
        """Test that unknown actions are ignored."""
        from gitlab_integrations.gitlab.webhooks import handle_issue_event

        payload = sample_issue_webhook_payload.copy()
        payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
        payload["object_attributes"]["action"] = "unknown_action"

        await handle_issue_event(payload)

        mock_slack_client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_description_truncation(self, mock_slack_client, sample_issue_webhook_payload):
        """Test that long descriptions are truncated."""
        from gitlab_integrations.gitlab.webhooks import handle_issue_event

        payload = sample_issue_webhook_payload.copy()
        payload["object_attributes"] = sample_issue_webhook_payload["object_attributes"].copy()
        payload["object_attributes"]["description"] = "A" * 300  # Long description

        await handle_issue_event(payload)

        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        blocks = call_args.kwargs["blocks"]

        # Find description block
        description_block = None
        for block in blocks:
            if block.get("type") == "section" and "Description" in str(block):
                description_block = block
                break

        if description_block:
            desc_text = description_block["text"]["text"]
            assert "..." in desc_text
            assert len(desc_text) < 250  # 200 chars + "..." + "*Description:*\n"
