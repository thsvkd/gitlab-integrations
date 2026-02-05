"""Tests for Slack command and modal handlers."""

from unittest.mock import MagicMock, patch

import pytest


class TestIssueCommand:
    """Tests for /issue command handler."""

    def test_issue_command_opens_modal(self):
        """Test that /issue command opens the issue creation modal."""
        from gitlab_integrations.slack.commands import register_commands

        # Create a mock app and test
        mock_app = MagicMock()
        register_commands(mock_app)

        # Verify command was registered
        mock_app.command.assert_called_with("/issue")

    def test_issue_status_command_with_valid_issue(self, mock_gitlab_client, mock_gitlab_issue):
        """Test /issue status command with valid issue number."""
        from gitlab_integrations.gitlab.api import get_issue_by_iid

        # The issue should be found
        result = get_issue_by_iid(123)
        assert result is not None
        assert result.iid == 123

    def test_issue_status_command_with_invalid_issue(self, mock_gitlab_client, mock_gitlab_project):
        """Test /issue status command with invalid issue number."""
        import gitlab
        from gitlab_integrations.gitlab.api import get_issue_by_iid

        mock_gitlab_project.issues.get.side_effect = gitlab.exceptions.GitlabGetError(
            response_code=404, error_message="Not found"
        )

        result = get_issue_by_iid(999)
        assert result is None


class TestIssueCreateModal:
    """Tests for issue creation modal."""

    def test_modal_structure_with_labels(self):
        """Test that modal has correct structure when labels are provided."""
        from gitlab_integrations.slack.modals import build_issue_create_modal

        labels = [
            {"name": "bug", "color": "#FF0000"},
            {"name": "feature", "color": "#00FF00"},
        ]
        modal = build_issue_create_modal(labels)

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "issue_create_modal"
        assert "title" in modal
        assert "submit" in modal
        assert "blocks" in modal

    def test_modal_structure_without_labels(self):
        """Test that modal has correct structure when no labels are provided."""
        from gitlab_integrations.slack.modals import build_issue_create_modal

        modal = build_issue_create_modal([])

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "issue_create_modal"
        # Should have title and description blocks, but no labels block
        block_ids = [block.get("block_id") for block in modal["blocks"]]
        assert "title_block" in block_ids
        assert "description_block" in block_ids
        assert "labels_block" not in block_ids

    def test_modal_has_required_fields(self):
        """Test that modal has all required input fields."""
        from gitlab_integrations.slack.modals import build_issue_create_modal

        labels = [{"name": "bug", "color": "#FF0000"}]
        modal = build_issue_create_modal(labels)

        blocks = modal["blocks"]
        block_ids = [block.get("block_id") for block in blocks]

        assert "title_block" in block_ids
        assert "description_block" in block_ids
        assert "labels_block" in block_ids

    def test_modal_label_options_from_gitlab(self):
        """Test that modal has label options from GitLab."""
        from gitlab_integrations.slack.modals import build_issue_create_modal

        labels = [
            {"name": "bug", "color": "#FF0000"},
            {"name": "feature", "color": "#00FF00"},
            {"name": "documentation", "color": "#0000FF"},
        ]
        modal = build_issue_create_modal(labels)

        labels_block = None
        for block in modal["blocks"]:
            if block.get("block_id") == "labels_block":
                labels_block = block
                break

        assert labels_block is not None
        options = labels_block["element"]["options"]
        option_values = [opt["value"] for opt in options]

        assert "bug" in option_values
        assert "feature" in option_values
        assert "documentation" in option_values

    def test_modal_uses_multi_select_for_labels(self):
        """Test that modal uses multi-select for labels."""
        from gitlab_integrations.slack.modals import build_issue_create_modal

        labels = [{"name": "bug", "color": "#FF0000"}]
        modal = build_issue_create_modal(labels)

        labels_block = None
        for block in modal["blocks"]:
            if block.get("block_id") == "labels_block":
                labels_block = block
                break

        assert labels_block["element"]["type"] == "multi_static_select"


class TestIssueCreation:
    """Tests for issue creation from modal submission."""

    def test_create_issue_with_labels(self, mock_gitlab_client, mock_gitlab_project, mock_gitlab_issue):
        """Test that issue is created with correct labels."""
        from gitlab_integrations.gitlab.api import create_issue

        labels = ["bug", "feature"]
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
        from gitlab_integrations.gitlab.api import create_issue

        result = create_issue(title="Test", description="Test")

        assert result.iid == 123
        assert result.web_url == "https://gitlab.test.com/project/issues/123"


class TestListLabels:
    """Tests for list_labels function."""

    def test_list_labels_returns_label_list(self, mock_gitlab_client, mock_gitlab_labels):
        """Test that list_labels returns label dictionaries."""
        from gitlab_integrations.gitlab.api import list_labels

        result = list_labels()

        assert len(result) == 3
        assert result[0]["name"] == "bug"
        assert result[0]["color"] == "#FF0000"
        assert result[1]["name"] == "feature"
        assert result[2]["name"] == "documentation"

    def test_list_labels_empty_project(self, mock_gitlab_client, mock_gitlab_project):
        """Test list_labels with project that has no labels."""
        from gitlab_integrations.gitlab.api import list_labels

        mock_gitlab_project.labels.list.return_value = []

        result = list_labels()

        assert result == []
