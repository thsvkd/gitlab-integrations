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


@pytest.fixture
def notion_client_with_mocks(mock_notion_client: MagicMock, sample_notion_page: dict):
    """Create a NotionClient with mocked SDK client and httpx."""
    with patch("gitlab_integrations.notion.api.httpx") as mock_httpx:
        client = NotionClient(token="test-token", database_id="test-db-id")
        client._client = mock_notion_client

        # Mock httpx.post for _query_database
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [sample_notion_page], "has_more": False}
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        yield client, mock_notion_client, mock_httpx


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

    def test_database_id_converts_to_uuid(self) -> None:
        """Test database_id converts 32-char string to UUID format."""
        client = NotionClient(token="test", database_id="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")
        assert client.database_id == "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"

    def test_create_page(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test creating a new Notion page."""
        client, mock_notion_client, _ = notion_client_with_mocks
        mock_notion_client.pages.create.return_value = sample_notion_page

        properties = {
            NotionProperties.TITLE: {"title": [{"text": {"content": "New Issue"}}]},
        }
        result = client.create_page(properties)

        mock_notion_client.pages.create.assert_called_once()
        assert result["id"] == "page-123"

    def test_get_page(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test retrieving a page by ID."""
        client, mock_notion_client, _ = notion_client_with_mocks
        mock_notion_client.pages.retrieve.return_value = sample_notion_page

        result = client.get_page("page-123")

        mock_notion_client.pages.retrieve.assert_called_once_with(page_id="page-123")
        assert result["id"] == "page-123"

    def test_get_page_by_gitlab_iid_found(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test finding page by GitLab IID when it exists."""
        client, _, mock_httpx = notion_client_with_mocks

        result = client.get_page_by_gitlab_iid(123)

        mock_httpx.post.assert_called_once()
        assert result is not None
        assert result["id"] == "page-123"

    def test_get_page_by_gitlab_iid_not_found(
        self,
        notion_client_with_mocks: tuple,
    ) -> None:
        """Test finding page by GitLab IID when it doesn't exist."""
        client, _, mock_httpx = notion_client_with_mocks

        # Override mock to return empty results
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [], "has_more": False}
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        result = client.get_page_by_gitlab_iid(999)

        assert result is None

    def test_update_page(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test updating an existing page."""
        client, mock_notion_client, _ = notion_client_with_mocks
        mock_notion_client.pages.update.return_value = sample_notion_page

        properties = {
            NotionProperties.STATUS: {"select": {"name": "closed"}},
        }
        result = client.update_page("page-123", properties)

        mock_notion_client.pages.update.assert_called_once_with(
            page_id="page-123",
            properties=properties,
        )
        assert result["id"] == "page-123"

    def test_archive_page(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test archiving a page."""
        client, mock_notion_client, _ = notion_client_with_mocks
        archived_page = {**sample_notion_page, "archived": True}
        mock_notion_client.pages.update.return_value = archived_page

        result = client.archive_page("page-123")

        mock_notion_client.pages.update.assert_called_once_with(
            page_id="page-123",
            archived=True,
        )
        assert result["archived"] is True

    def test_query_modified_pages(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test querying modified pages without time filter."""
        client, _, mock_httpx = notion_client_with_mocks

        result = client.query_modified_pages()

        assert len(result) == 1
        assert result[0]["id"] == "page-123"

    def test_query_modified_pages_with_since_filter(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test querying modified pages with time filter."""
        client, _, _ = notion_client_with_mocks

        # Filter for pages modified after 2024-01-01
        result = client.query_modified_pages(since="2024-01-01T00:00:00+00:00")

        assert len(result) == 1

    def test_query_modified_pages_pagination(
        self,
        notion_client_with_mocks: tuple,
        sample_notion_page: dict,
    ) -> None:
        """Test querying pages with pagination."""
        client, _, mock_httpx = notion_client_with_mocks
        page2 = {**sample_notion_page, "id": "page-456"}

        # Setup pagination responses
        responses = [
            MagicMock(
                json=MagicMock(return_value={
                    "results": [sample_notion_page],
                    "has_more": True,
                    "next_cursor": "cursor-1",
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "results": [page2],
                    "has_more": False,
                }),
                raise_for_status=MagicMock(),
            ),
        ]
        mock_httpx.post.side_effect = responses

        result = client.query_modified_pages()

        assert len(result) == 2
        assert mock_httpx.post.call_count == 2


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
