"""
Tests for Notion synchronization logic.

This module tests the bidirectional sync between GitLab issues
and Notion database pages.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Set test environment variables before importing
os.environ.setdefault("NOTION_TOKEN", "test-notion-token")
os.environ.setdefault("NOTION_DATABASE_ID", "test-database-id")
os.environ.setdefault("NOTION_SYNC_ENABLED", "true")

from gitlab_integrations.notion.schemas import (
    NotionProperties,
    extract_gitlab_iid_from_page,
    extract_last_synced_from_page,
    gitlab_issue_to_notion_properties,
    notion_page_to_gitlab_update,
)
from gitlab_integrations.notion.sync import (
    check_conflict,
    resolve_conflict_lww,
    sync_gitlab_to_notion,
    sync_modified_notion_pages,
    sync_notion_to_gitlab,
)


@pytest.fixture
def sample_gitlab_issue_data() -> dict:
    """Create sample GitLab issue data."""
    return {
        "iid": 123,
        "title": "Test Issue",
        "description": "Test description",
        "state": "opened",
        "labels": ["bug", "high"],
        "web_url": "https://gitlab.test.com/project/issues/123",
        "author": {"name": "Test User"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


@pytest.fixture
def sample_notion_page() -> dict:
    """Create sample Notion page."""
    return {
        "id": "page-123",
        "last_edited_time": "2024-01-02T00:00:00.000Z",
        "properties": {
            NotionProperties.TITLE: {
                "title": [{"text": {"content": "Test Issue"}}]
            },
            NotionProperties.STATUS: {
                "select": {"name": "opened"}
            },
            NotionProperties.GITLAB_IID: {
                "number": 123
            },
            NotionProperties.GITLAB_URL: {
                "url": "https://gitlab.test.com/project/issues/123"
            },
            NotionProperties.DESCRIPTION: {
                "rich_text": [{"text": {"content": "Test description"}}]
            },
            NotionProperties.LABELS: {
                "multi_select": [{"name": "bug"}, {"name": "high"}]
            },
            NotionProperties.LAST_SYNCED: {
                "date": {"start": "2024-01-01T12:00:00"}
            },
        },
    }


@pytest.fixture
def mock_gitlab_issue() -> MagicMock:
    """Create mock GitLab issue."""
    issue = MagicMock()
    issue.iid = 123
    issue.title = "Test Issue"
    issue.description = "Test description"
    issue.state = "opened"
    issue.labels = ["bug", "high"]
    issue.web_url = "https://gitlab.test.com/project/issues/123"
    issue.updated_at = "2024-01-02T00:00:00Z"
    return issue


class TestSchemaConversions:
    """Tests for schema conversion functions."""

    def test_gitlab_issue_to_notion_properties(
        self, sample_gitlab_issue_data: dict
    ) -> None:
        """Test converting GitLab issue to Notion properties."""
        properties = gitlab_issue_to_notion_properties(sample_gitlab_issue_data)

        assert properties[NotionProperties.TITLE]["title"][0]["text"]["content"] == "Test Issue"
        assert properties[NotionProperties.STATUS]["select"]["name"] == "opened"
        assert properties[NotionProperties.GITLAB_IID]["number"] == 123
        assert properties[NotionProperties.GITLAB_URL]["url"] == "https://gitlab.test.com/project/issues/123"
        assert len(properties[NotionProperties.LABELS]["multi_select"]) == 2

    def test_gitlab_issue_to_notion_properties_minimal(self) -> None:
        """Test conversion with minimal issue data."""
        issue_data = {
            "iid": 1,
            "title": "Minimal Issue",
            "state": "opened",
        }
        properties = gitlab_issue_to_notion_properties(issue_data)

        assert properties[NotionProperties.TITLE]["title"][0]["text"]["content"] == "Minimal Issue"
        assert properties[NotionProperties.GITLAB_IID]["number"] == 1

    def test_notion_page_to_gitlab_update(self, sample_notion_page: dict) -> None:
        """Test converting Notion page to GitLab update data."""
        update_data = notion_page_to_gitlab_update(sample_notion_page)

        assert update_data["title"] == "Test Issue"
        assert update_data["description"] == "Test description"
        assert update_data["state_event"] == "reopen"  # opened status maps to reopen event
        assert update_data["labels"] == ["bug", "high"]

    def test_notion_page_to_gitlab_update_closed(self, sample_notion_page: dict) -> None:
        """Test conversion when Notion status is closed."""
        sample_notion_page["properties"][NotionProperties.STATUS] = {
            "select": {"name": "closed"}
        }
        update_data = notion_page_to_gitlab_update(sample_notion_page)

        assert update_data["state_event"] == "close"

    def test_extract_gitlab_iid_from_page(self, sample_notion_page: dict) -> None:
        """Test extracting GitLab IID from Notion page."""
        iid = extract_gitlab_iid_from_page(sample_notion_page)
        assert iid == 123

    def test_extract_gitlab_iid_from_page_missing(self) -> None:
        """Test extracting IID when not present."""
        page = {"properties": {}}
        iid = extract_gitlab_iid_from_page(page)
        assert iid is None

    def test_extract_last_synced_from_page(self, sample_notion_page: dict) -> None:
        """Test extracting last synced timestamp."""
        last_synced = extract_last_synced_from_page(sample_notion_page)
        assert last_synced is not None
        assert last_synced.year == 2024


class TestSyncGitlabToNotion:
    """Tests for GitLab to Notion sync."""

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_creates_new_page(
        self,
        mock_get_client: MagicMock,
        mock_settings: MagicMock,
        sample_gitlab_issue_data: dict,
    ) -> None:
        """Test sync creates a new page when none exists."""
        mock_settings.notion_sync_enabled = True
        mock_client = MagicMock()
        mock_client.get_page_by_gitlab_iid.return_value = None
        mock_client.create_page.return_value = {"id": "new-page"}
        mock_get_client.return_value = mock_client

        result = sync_gitlab_to_notion(sample_gitlab_issue_data)

        mock_client.create_page.assert_called_once()
        assert result["id"] == "new-page"

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_updates_existing_page(
        self,
        mock_get_client: MagicMock,
        mock_settings: MagicMock,
        sample_gitlab_issue_data: dict,
        sample_notion_page: dict,
    ) -> None:
        """Test sync updates existing page."""
        mock_settings.notion_sync_enabled = True
        mock_client = MagicMock()
        mock_client.get_page_by_gitlab_iid.return_value = sample_notion_page
        mock_client.update_page.return_value = sample_notion_page
        mock_get_client.return_value = mock_client

        sync_gitlab_to_notion(sample_gitlab_issue_data)

        mock_client.update_page.assert_called_once()
        mock_client.create_page.assert_not_called()

    @patch("gitlab_integrations.notion.sync.settings")
    def test_sync_disabled_returns_none(
        self,
        mock_settings: MagicMock,
        sample_gitlab_issue_data: dict,
    ) -> None:
        """Test sync returns None when disabled."""
        mock_settings.notion_sync_enabled = False

        result = sync_gitlab_to_notion(sample_gitlab_issue_data)

        assert result is None

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_without_iid_returns_none(
        self,
        mock_get_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test sync returns None when issue has no IID."""
        mock_settings.notion_sync_enabled = True
        issue_data = {"title": "No IID Issue"}

        result = sync_gitlab_to_notion(issue_data)

        assert result is None


class TestSyncNotionToGitlab:
    """Tests for Notion to GitLab sync."""

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.gitlab_api")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_updates_gitlab_issue(
        self,
        mock_get_client: MagicMock,
        mock_gitlab_api: MagicMock,
        mock_settings: MagicMock,
        sample_notion_page: dict,
        mock_gitlab_issue: MagicMock,
    ) -> None:
        """Test sync updates GitLab issue from Notion page."""
        mock_settings.notion_sync_enabled = True
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_gitlab_api.get_issue_by_iid.return_value = mock_gitlab_issue

        mock_project = MagicMock()
        mock_project.issues.get.return_value = mock_gitlab_issue
        mock_gitlab_api.get_project.return_value = mock_project

        result = sync_notion_to_gitlab(sample_notion_page)

        assert result is True
        mock_gitlab_issue.save.assert_called_once()

    @patch("gitlab_integrations.notion.sync.settings")
    def test_sync_disabled_returns_false(
        self,
        mock_settings: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test sync returns False when disabled."""
        mock_settings.notion_sync_enabled = False

        result = sync_notion_to_gitlab(sample_notion_page)

        assert result is False

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.gitlab_api")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_handles_missing_gitlab_issue(
        self,
        mock_get_client: MagicMock,
        mock_gitlab_api: MagicMock,
        mock_settings: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test sync handles missing GitLab issue gracefully."""
        mock_settings.notion_sync_enabled = True
        mock_gitlab_api.get_issue_by_iid.return_value = None

        result = sync_notion_to_gitlab(sample_notion_page)

        assert result is False


class TestConflictResolution:
    """Tests for conflict detection and resolution."""

    def test_check_conflict_no_conflict(
        self,
        sample_notion_page: dict,
        mock_gitlab_issue: MagicMock,
    ) -> None:
        """Test no conflict when only one side modified."""
        # GitLab modified after last sync, Notion not modified
        sample_notion_page["last_edited_time"] = "2024-01-01T00:00:00.000Z"

        has_conflict, winner = check_conflict(sample_notion_page, mock_gitlab_issue)

        assert has_conflict is False
        assert winner is None

    def test_check_conflict_both_modified(
        self,
        sample_notion_page: dict,
        mock_gitlab_issue: MagicMock,
    ) -> None:
        """Test conflict detected when both sides modified."""
        # Both modified after last sync
        sample_notion_page["last_edited_time"] = "2024-01-02T00:00:00.000Z"
        mock_gitlab_issue.updated_at = "2024-01-03T00:00:00Z"

        has_conflict, winner = check_conflict(sample_notion_page, mock_gitlab_issue)

        assert has_conflict is True
        assert winner == "gitlab"  # GitLab is newer

    def test_resolve_conflict_lww_notion_wins(self) -> None:
        """Test LWW resolves to Notion when it's newer."""
        notion_time = datetime(2024, 1, 2)
        gitlab_time = datetime(2024, 1, 1)

        winner = resolve_conflict_lww(notion_time, gitlab_time)

        assert winner == "notion"

    def test_resolve_conflict_lww_gitlab_wins(self) -> None:
        """Test LWW resolves to GitLab when it's newer."""
        notion_time = datetime(2024, 1, 1)
        gitlab_time = datetime(2024, 1, 2)

        winner = resolve_conflict_lww(notion_time, gitlab_time)

        assert winner == "gitlab"

    def test_resolve_conflict_lww_none_notion(self) -> None:
        """Test LWW with None Notion timestamp."""
        winner = resolve_conflict_lww(None, datetime(2024, 1, 1))
        assert winner == "gitlab"

    def test_resolve_conflict_lww_none_gitlab(self) -> None:
        """Test LWW with None GitLab timestamp."""
        winner = resolve_conflict_lww(datetime(2024, 1, 1), None)
        assert winner == "notion"


class TestSyncModifiedNotionPages:
    """Tests for batch Notion sync."""

    @patch("gitlab_integrations.notion.sync.settings")
    def test_sync_disabled_returns_empty_stats(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test returns empty stats when sync disabled."""
        mock_settings.notion_sync_enabled = False

        stats = sync_modified_notion_pages()

        assert stats == {"total": 0, "synced": 0, "skipped": 0, "failed": 0}

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.gitlab_api")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_processes_pages(
        self,
        mock_get_client: MagicMock,
        mock_gitlab_api: MagicMock,
        mock_settings: MagicMock,
        sample_notion_page: dict,
        mock_gitlab_issue: MagicMock,
    ) -> None:
        """Test sync processes multiple pages."""
        mock_settings.notion_sync_enabled = True

        mock_client = MagicMock()
        mock_client.query_modified_pages.return_value = [sample_notion_page]
        mock_get_client.return_value = mock_client

        mock_gitlab_api.get_issue_by_iid.return_value = mock_gitlab_issue
        mock_project = MagicMock()
        mock_project.issues.get.return_value = mock_gitlab_issue
        mock_gitlab_api.get_project.return_value = mock_project

        stats = sync_modified_notion_pages()

        assert stats["total"] == 1

    @patch("gitlab_integrations.notion.sync.settings")
    @patch("gitlab_integrations.notion.sync.get_notion_client")
    def test_sync_skips_pages_without_iid(
        self,
        mock_get_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test sync skips pages without GitLab IID."""
        mock_settings.notion_sync_enabled = True

        page_without_iid = {"id": "page-1", "properties": {}}
        mock_client = MagicMock()
        mock_client.query_modified_pages.return_value = [page_without_iid]
        mock_get_client.return_value = mock_client

        stats = sync_modified_notion_pages()

        assert stats["total"] == 1
        assert stats["skipped"] == 1
