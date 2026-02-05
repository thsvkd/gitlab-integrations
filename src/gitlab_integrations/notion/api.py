"""
Notion API client module.

This module provides a client for interacting with the Notion API,
including page creation, retrieval, update, and querying.
"""

import logging
from typing import Any

import httpx
from notion_client import Client

from gitlab_integrations.config import settings
from gitlab_integrations.notion.schemas import NotionProperties

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """
    Client for Notion API operations.

    Provides methods for CRUD operations on Notion pages
    within the configured database.
    """

    def __init__(self, token: str | None = None, database_id: str | None = None):
        """
        Initialize Notion client.

        Args:
            token: Notion integration token. Defaults to settings.notion_token.
            database_id: Target database ID. Defaults to settings.notion_database_id.
        """
        self._token = token or settings.notion_token
        self._database_id = database_id or settings.notion_database_id
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """
        Get or create Notion client instance.

        Returns:
            Client: Notion API client.

        Raises:
            ValueError: If notion_token is not configured.
        """
        if self._client is None:
            if not self._token:
                raise ValueError("Notion token is not configured")
            self._client = Client(auth=self._token)
        return self._client

    @property
    def database_id(self) -> str:
        """
        Get configured database ID in UUID format.

        Returns:
            str: Notion database ID.

        Raises:
            ValueError: If notion_database_id is not configured.
        """
        if not self._database_id:
            raise ValueError("Notion database ID is not configured")
        # Convert to UUID format if needed
        db_id = self._database_id
        if len(db_id) == 32 and "-" not in db_id:
            db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"
        return db_id

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for Notion API requests."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _query_database(
        self,
        filter_conditions: dict[str, Any] | None = None,
        page_size: int = 100,
        start_cursor: str | None = None,
    ) -> dict[str, Any]:
        """
        Query database using direct HTTP request.

        Args:
            filter_conditions: Optional filter for the query.
            page_size: Number of results per page.
            start_cursor: Cursor for pagination.

        Returns:
            dict[str, Any]: Query response.
        """
        body: dict[str, Any] = {"page_size": page_size}
        if filter_conditions:
            body["filter"] = filter_conditions
        if start_cursor:
            body["start_cursor"] = start_cursor

        url = f"{NOTION_API_BASE}/databases/{self.database_id}/query"
        response = httpx.post(url, headers=self._get_headers(), json=body)
        response.raise_for_status()
        return response.json()

    def create_page(self, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new page in the Notion database.

        Args:
            properties: Page properties formatted for Notion API.

        Returns:
            dict[str, Any]: Created page object.

        Example:
            >>> client = NotionClient()
            >>> page = client.create_page({
            ...     "Title": {"title": [{"text": {"content": "New Issue"}}]},
            ...     "Status": {"select": {"name": "opened"}},
            ... })
        """
        logger.info("Creating Notion page")
        response = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )
        logger.info(f"Created Notion page: {response.get('id')}")
        return response

    def get_page(self, page_id: str) -> dict[str, Any]:
        """
        Get a page by its ID.

        Args:
            page_id: Notion page ID.

        Returns:
            dict[str, Any]: Page object.
        """
        return self.client.pages.retrieve(page_id=page_id)

    def get_page_by_gitlab_iid(self, gitlab_iid: int) -> dict[str, Any] | None:
        """
        Find a Notion page by GitLab issue IID.

        Args:
            gitlab_iid: GitLab issue number.

        Returns:
            dict[str, Any] | None: Page object if found, None otherwise.
        """
        logger.debug(f"Searching for page with GitLab IID: {gitlab_iid}")
        response = self._query_database(
            filter_conditions={
                "property": NotionProperties.GITLAB_IID,
                "number": {"equals": gitlab_iid},
            },
        )
        results = response.get("results", [])
        if results:
            logger.debug(f"Found page for GitLab IID {gitlab_iid}")
            return results[0]
        logger.debug(f"No page found for GitLab IID {gitlab_iid}")
        return None

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing page.

        Args:
            page_id: Notion page ID to update.
            properties: Updated properties.

        Returns:
            dict[str, Any]: Updated page object.
        """
        logger.info(f"Updating Notion page: {page_id}")
        response = self.client.pages.update(
            page_id=page_id,
            properties=properties,
        )
        return response

    def archive_page(self, page_id: str) -> dict[str, Any]:
        """
        Archive (soft delete) a page.

        Args:
            page_id: Notion page ID to archive.

        Returns:
            dict[str, Any]: Archived page object.
        """
        logger.info(f"Archiving Notion page: {page_id}")
        response = self.client.pages.update(
            page_id=page_id,
            archived=True,
        )
        return response

    def query_modified_pages(
        self,
        since: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query pages modified since a given timestamp.

        This method retrieves all pages from the database and filters
        them by last_edited_time. Used for polling Notion changes.

        Args:
            since: ISO timestamp to filter pages modified after this time.
                   If None, returns all non-archived pages.
            page_size: Number of pages to retrieve per request.

        Returns:
            list[dict[str, Any]]: List of modified page objects.
        """
        logger.debug(f"Querying modified pages since: {since}")

        # Build filter - only get non-archived pages with GitLab IID
        filter_conditions: dict[str, Any] = {
            "property": NotionProperties.GITLAB_IID,
            "number": {"is_not_empty": True},
        }

        all_pages: list[dict[str, Any]] = []
        has_more = True
        start_cursor: str | None = None

        while has_more:
            response = self._query_database(
                filter_conditions=filter_conditions,
                page_size=page_size,
                start_cursor=start_cursor,
            )
            all_pages.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        # Filter by last_edited_time if since is provided
        if since:
            from datetime import datetime

            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            filtered_pages = []
            for page in all_pages:
                last_edited = page.get("last_edited_time")
                if last_edited:
                    page_dt = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                    if page_dt > since_dt:
                        filtered_pages.append(page)
            all_pages = filtered_pages

        logger.debug(f"Found {len(all_pages)} modified pages")
        return all_pages

    def query_all_pages(self, page_size: int = 100) -> list[dict[str, Any]]:
        """
        Query all pages in the database with GitLab IID.

        Args:
            page_size: Number of pages to retrieve per request.

        Returns:
            list[dict[str, Any]]: List of all page objects.
        """
        return self.query_modified_pages(since=None, page_size=page_size)

    def query_database_all(self, page_size: int = 100) -> list[dict[str, Any]]:
        """
        Query all pages in the database (no filter).

        Args:
            page_size: Number of pages to retrieve per request.

        Returns:
            list[dict[str, Any]]: List of all page objects.
        """
        logger.debug("Querying all pages from database")

        all_pages: list[dict[str, Any]] = []
        has_more = True
        start_cursor: str | None = None

        while has_more:
            response = self._query_database(
                filter_conditions=None,
                page_size=page_size,
                start_cursor=start_cursor,
            )
            all_pages.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        logger.debug(f"Found {len(all_pages)} total pages")
        return all_pages

    def query_unsynced_pages(self, page_size: int = 100) -> list[dict[str, Any]]:
        """
        Query pages without GitLab IID (unsynced to GitLab).

        Args:
            page_size: Number of pages to retrieve per request.

        Returns:
            list[dict[str, Any]]: List of unsynced page objects.
        """
        logger.debug("Querying unsynced pages (no GitLab IID)")

        filter_conditions: dict[str, Any] = {
            "property": NotionProperties.GITLAB_IID,
            "number": {"is_empty": True},
        }

        all_pages: list[dict[str, Any]] = []
        has_more = True
        start_cursor: str | None = None

        while has_more:
            response = self._query_database(
                filter_conditions=filter_conditions,
                page_size=page_size,
                start_cursor=start_cursor,
            )
            all_pages.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        logger.debug(f"Found {len(all_pages)} unsynced pages")
        return all_pages

    def update_sync_status(
        self,
        page_id: str,
        synced: bool,
        sync_error: str | None = None,
        gitlab_iid: int | None = None,
        gitlab_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Update sync status fields on a Notion page.

        Args:
            page_id: Notion page ID to update.
            synced: Whether sync was successful.
            sync_error: Error message if sync failed.
            gitlab_iid: GitLab issue IID if created.
            gitlab_url: GitLab issue URL if created.

        Returns:
            dict[str, Any]: Updated page object.
        """
        from datetime import datetime, timezone

        logger.info(f"Updating sync status for page {page_id}: synced={synced}")

        properties: dict[str, Any] = {
            NotionProperties.SYNCED: {"checkbox": synced},
            NotionProperties.LAST_SYNCED: {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            },
        }

        # Set or clear sync error
        if sync_error:
            properties[NotionProperties.SYNC_ERROR] = {
                "rich_text": [{"text": {"content": sync_error[:2000]}}]
            }
        else:
            properties[NotionProperties.SYNC_ERROR] = {"rich_text": []}

        # Update GitLab IID if provided
        if gitlab_iid is not None:
            properties[NotionProperties.GITLAB_IID] = {"number": gitlab_iid}

        # Update GitLab URL if provided
        if gitlab_url is not None:
            properties[NotionProperties.GITLAB_URL] = {"url": gitlab_url}

        return self.update_page(page_id, properties)


# Global client instance (lazy initialization)
_notion_client: NotionClient | None = None


def get_notion_client() -> NotionClient:
    """
    Get or create the global Notion client instance.

    Returns:
        NotionClient: Notion client instance.
    """
    global _notion_client
    if _notion_client is None:
        _notion_client = NotionClient()
    return _notion_client

