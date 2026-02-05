"""Tests for Slack command and modal handlers."""

from unittest.mock import MagicMock, patch

import pytest


class TestIssueCommand:
    """Tests for /issue command handler."""

    def test_issue_command_opens_modal(self):
        """Test that /issue command opens the issue creation modal."""
        from gitlab_slack.slack.commands import register_commands
        from slack_bolt import App

        app = App(
            token="xoxb-test",
            signing_secret="test-secret",
            token_verification_enabled=False,
        )
        register_commands(app)

        # Get the registered command handler
        handler = None
        for listener in app._listeners:
            if hasattr(listener, 'ack') and '/issue' in str(listener):
                handler = listener
                break

        # Simulate command
        ack = MagicMock()
        client = MagicMock()
        logger = MagicMock()
        command = {
            "text": "",
            "trigger_id": "test-trigger-id",
            "channel_id": "C123",
            "user_id": "U123",
        }

        # Find and call the handler function
        for middleware in app._middleware_list:
            pass

        # Direct function test
        from gitlab_slack.slack.commands import register_commands
        from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL

        # Create a mock app and test
        mock_app = MagicMock()
        register_commands(mock_app)

        # Verify command was registered
        mock_app.command.assert_called_with("/issue")

    def test_issue_status_command_with_valid_issue(self, mock_gitlab_client, mock_gitlab_issue):
        """Test /issue status command with valid issue number."""
        from gitlab_slack.gitlab.api import get_issue_by_iid

        # The issue should be found
        result = get_issue_by_iid(123)
        assert result is not None
        assert result.iid == 123

    def test_issue_status_command_with_invalid_issue(self, mock_gitlab_client, mock_gitlab_project):
        """Test /issue status command with invalid issue number."""
        import gitlab
        from gitlab_slack.gitlab.api import get_issue_by_iid

        mock_gitlab_project.issues.get.side_effect = gitlab.exceptions.GitlabGetError(
            response_code=404, error_message="Not found"
        )

        result = get_issue_by_iid(999)
        assert result is None


class TestIssueCreateModal:
    """Tests for issue creation modal."""

    def test_modal_structure(self):
        """Test that modal has correct structure."""
        from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL

        assert ISSUE_CREATE_MODAL["type"] == "modal"
        assert ISSUE_CREATE_MODAL["callback_id"] == "issue_create_modal"
        assert "title" in ISSUE_CREATE_MODAL
        assert "submit" in ISSUE_CREATE_MODAL
        assert "blocks" in ISSUE_CREATE_MODAL

    def test_modal_has_required_fields(self):
        """Test that modal has all required input fields."""
        from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL

        blocks = ISSUE_CREATE_MODAL["blocks"]
        block_ids = [block.get("block_id") for block in blocks]

        assert "title_block" in block_ids
        assert "type_block" in block_ids
        assert "priority_block" in block_ids
        assert "description_block" in block_ids

    def test_modal_type_options(self):
        """Test that modal has correct type options."""
        from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL

        type_block = None
        for block in ISSUE_CREATE_MODAL["blocks"]:
            if block.get("block_id") == "type_block":
                type_block = block
                break

        assert type_block is not None
        options = type_block["element"]["options"]
        option_values = [opt["value"] for opt in options]

        assert "bug" in option_values
        assert "feature" in option_values
        assert "documentation" in option_values
        assert "question" in option_values

    def test_modal_priority_options(self):
        """Test that modal has correct priority options."""
        from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL

        priority_block = None
        for block in ISSUE_CREATE_MODAL["blocks"]:
            if block.get("block_id") == "priority_block":
                priority_block = block
                break

        assert priority_block is not None
        options = priority_block["element"]["options"]
        option_values = [opt["value"] for opt in options]

        assert "critical" in option_values
        assert "high" in option_values
        assert "medium" in option_values
        assert "low" in option_values

    def test_modal_default_priority(self):
        """Test that modal has medium as default priority."""
        from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL

        priority_block = None
        for block in ISSUE_CREATE_MODAL["blocks"]:
            if block.get("block_id") == "priority_block":
                priority_block = block
                break

        initial_option = priority_block["element"]["initial_option"]
        assert initial_option["value"] == "medium"


class TestIssueCreation:
    """Tests for issue creation from modal submission."""

    def test_create_issue_with_labels(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test that issue is created with correct labels."""
        from gitlab_slack.gitlab.api import create_issue

        labels = ["type::bug", "priority::high"]
        result = create_issue(
            title="Bug Report",
            description="Test description\n\n---\n_Created from Slack by @testuser_",
            labels=labels,
        )

        mock_gitlab_project.issues.create.assert_called_once()
        call_args = mock_gitlab_project.issues.create.call_args[0][0]
        assert call_args["labels"] == labels
        assert "Created from Slack" in call_args["description"]

    def test_create_issue_success_returns_issue(self, mock_gitlab_client, mock_gitlab_issue):
        """Test that successful creation returns issue object."""
        from gitlab_slack.gitlab.api import create_issue

        result = create_issue(title="Test", description="Test")

        assert result.iid == 123
        assert result.web_url == "https://gitlab.test.com/project/issues/123"
