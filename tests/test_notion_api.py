"""
Tests for Notion API client.

This module tests the NotionClient class and its methods
for interacting with the Notion API.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set test environment variables before importing
os.environ.setdefault("NOTION_TOKEN", "test-notion-token")
os.environ.setdefault("NOTION_DATABASE_ID", "test-database-id")
os.environ.setdefault("NOTION_SYNC_ENABLED", "true")

from gitlab_integrations.notion.api import NotionClient, get_notion_client
from gitlab_integrations.notion.schemas import NotionProperties


@pytest.fixture
def mock_notion_client() -> MagicMock:
    """Create a mock Notion SDK client."""
    return MagicMock()


@pytest.fixture
def notion_client(mock_notion_client: MagicMock) -> NotionClient:
    """Create a NotionClient with mocked SDK client."""
    client = NotionClient(token="test-token", database_id="test-db-id")
    client._client = mock_notion_client
    return client


@pytest.fixture
def sample_notion_page() -> dict:
    """Create a sample Notion page response."""
    return {
        "id": "page-123",
        "object": "page",
        "created_time": "2024-01-01T00:00:00.000Z",
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
            NotionProperties.AUTHOR: {
                "rich_text": [{"text": {"content": "Test User"}}]
            },
        },
    }


class TestNotionClient:
    """Tests for NotionClient class."""

    def test_client_initialization(self) -> None:
        """Test client initializes with provided credentials."""
        client = NotionClient(token="my-token", database_id="my-db")
        assert client._token == "my-token"
        assert client._database_id == "my-db"

    def test_client_raises_error_without_token(self) -> None:
        """Test client raises error when accessing without token."""
        with patch("gitlab_integrations.notion.api.settings") as mock_settings:
            mock_settings.notion_token = None
            mock_settings.notion_database_id = "my-db"
            client = NotionClient(token=None, database_id="my-db")
            # Override the token to ensure it's None
            client._token = None
            with pytest.raises(ValueError, match="Notion token is not configured"):
                _ = client.client

    def test_client_raises_error_without_database_id(self) -> None:
        """Test client raises error when database_id not set."""
        with patch("gitlab_integrations.notion.api.settings") as mock_settings:
            mock_settings.notion_token = "my-token"
            mock_settings.notion_database_id = None
            client = NotionClient(token="my-token", database_id=None)
            # Override the database_id to ensure it's None
            client._database_id = None
            with pytest.raises(ValueError, match="Notion database ID is not configured"):
                _ = client.database_id

    def test_create_page(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test creating a new Notion page."""
        mock_notion_client.pages.create.return_value = sample_notion_page

        properties = {
            NotionProperties.TITLE: {"title": [{"text": {"content": "New Issue"}}]},
        }
        result = notion_client.create_page(properties)

        mock_notion_client.pages.create.assert_called_once_with(
            parent={"database_id": "test-db-id"},
            properties=properties,
        )
        assert result["id"] == "page-123"

    def test_get_page(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test retrieving a page by ID."""
        mock_notion_client.pages.retrieve.return_value = sample_notion_page

        result = notion_client.get_page("page-123")

        mock_notion_client.pages.retrieve.assert_called_once_with(page_id="page-123")
        assert result["id"] == "page-123"

    def test_get_page_by_gitlab_iid_found(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test finding page by GitLab IID when it exists."""
        mock_notion_client.databases.query.return_value = {
            "results": [sample_notion_page]
        }

        result = notion_client.get_page_by_gitlab_iid(123)

        mock_notion_client.databases.query.assert_called_once()
        assert result is not None
        assert result["id"] == "page-123"

    def test_get_page_by_gitlab_iid_not_found(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
    ) -> None:
        """Test finding page by GitLab IID when it doesn't exist."""
        mock_notion_client.databases.query.return_value = {"results": []}

        result = notion_client.get_page_by_gitlab_iid(999)

        assert result is None

    def test_update_page(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test updating an existing page."""
        mock_notion_client.pages.update.return_value = sample_notion_page

        properties = {
            NotionProperties.STATUS: {"select": {"name": "closed"}},
        }
        result = notion_client.update_page("page-123", properties)

        mock_notion_client.pages.update.assert_called_once_with(
            page_id="page-123",
            properties=properties,
        )
        assert result["id"] == "page-123"

    def test_archive_page(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test archiving a page."""
        archived_page = {**sample_notion_page, "archived": True}
        mock_notion_client.pages.update.return_value = archived_page

        result = notion_client.archive_page("page-123")

        mock_notion_client.pages.update.assert_called_once_with(
            page_id="page-123",
            archived=True,
        )
        assert result["archived"] is True

    def test_query_modified_pages(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test querying modified pages without time filter."""
        mock_notion_client.databases.query.return_value = {
            "results": [sample_notion_page],
            "has_more": False,
        }

        result = notion_client.query_modified_pages()

        assert len(result) == 1
        assert result[0]["id"] == "page-123"

    def test_query_modified_pages_with_since_filter(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test querying modified pages with time filter."""
        # Page was edited on 2024-01-02
        mock_notion_client.databases.query.return_value = {
            "results": [sample_notion_page],
            "has_more": False,
        }

        # Filter for pages modified after 2024-01-01
        result = notion_client.query_modified_pages(since="2024-01-01T00:00:00+00:00")

        assert len(result) == 1

    def test_query_modified_pages_pagination(
        self,
        notion_client: NotionClient,
        mock_notion_client: MagicMock,
        sample_notion_page: dict,
    ) -> None:
        """Test querying pages with pagination."""
        page2 = {**sample_notion_page, "id": "page-456"}

        mock_notion_client.databases.query.side_effect = [
            {
                "results": [sample_notion_page],
                "has_more": True,
                "next_cursor": "cursor-1",
            },
            {
                "results": [page2],
                "has_more": False,
            },
        ]

        result = notion_client.query_modified_pages()

        assert len(result) == 2
        assert mock_notion_client.databases.query.call_count == 2


class TestGetNotionClient:
    """Tests for get_notion_client function."""

    def test_get_notion_client_returns_singleton(self) -> None:
        """Test that get_notion_client returns the same instance."""
        with patch("gitlab_integrations.notion.api._notion_client", None):
            with patch("gitlab_integrations.notion.api.settings") as mock_settings:
                mock_settings.notion_token = "test-token"
                mock_settings.notion_database_id = "test-db"

                client1 = get_notion_client()
                # Manually set the global to simulate singleton behavior
                import gitlab_integrations.notion.api as api_module
                api_module._notion_client = client1
                client2 = get_notion_client()

                assert client1 is client2
