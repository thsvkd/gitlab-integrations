"""
Notion data schemas and conversion utilities.

This module defines the Notion database schema and provides functions
to convert between GitLab issue format and Notion page properties.
"""

from datetime import datetime, timezone
from typing import Any


# Notion database property names
class NotionProperties:
    """Notion database property names."""

    TITLE = "Title"
    STATUS = "Status"
    LABELS = "Labels"
    GITLAB_IID = "GitLab IID"
    GITLAB_URL = "GitLab URL"
    AUTHOR = "Author"
    DESCRIPTION = "Description"
    CREATED_AT = "Created At"
    UPDATED_AT = "Updated At"
    LAST_SYNCED = "Last Synced"
    SYNCED = "Synced"
    SYNC_ERROR = "Sync Error"


# Status mapping between GitLab and Notion
GITLAB_TO_NOTION_STATUS = {
    "opened": "opened",
    "closed": "closed",
}

NOTION_TO_GITLAB_STATUS = {
    "opened": "opened",
    "closed": "closed",
}


def gitlab_issue_to_notion_properties(
    issue_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert GitLab issue data to Notion page properties.

    Args:
        issue_data: GitLab issue data containing:
            - iid: Issue number
            - title: Issue title
            - description: Issue description
            - state: Issue state (opened/closed)
            - labels: List of label names
            - web_url: URL to the issue
            - author: Author information
            - created_at: Creation timestamp
            - updated_at: Update timestamp

    Returns:
        dict[str, Any]: Notion page properties formatted for API.
    """
    properties: dict[str, Any] = {
        NotionProperties.TITLE: {
            "title": [{"text": {"content": issue_data.get("title", "")}}]
        },
        NotionProperties.STATUS: {
            "select": {"name": GITLAB_TO_NOTION_STATUS.get(
                issue_data.get("state", "opened"), "opened"
            )}
        },
        NotionProperties.GITLAB_IID: {
            "number": issue_data.get("iid")
        },
        NotionProperties.GITLAB_URL: {
            "url": issue_data.get("web_url") or issue_data.get("url")
        },
        NotionProperties.LAST_SYNCED: {
            "date": {"start": datetime.now(timezone.utc).isoformat()}
        },
    }

    # Add labels if present
    labels = issue_data.get("labels", [])
    if labels:
        properties[NotionProperties.LABELS] = {
            "multi_select": [{"name": label} for label in labels]
        }

    # Add author if present
    author = issue_data.get("author")
    if author:
        author_name = author.get("name", "") if isinstance(author, dict) else str(author)
        properties[NotionProperties.AUTHOR] = {
            "rich_text": [{"text": {"content": author_name}}]
        }

    # Add description if present
    description = issue_data.get("description", "") or ""
    if description:
        # Truncate description to 2000 characters (Notion limit)
        truncated_desc = description[:2000]
        properties[NotionProperties.DESCRIPTION] = {
            "rich_text": [{"text": {"content": truncated_desc}}]
        }

    # Add created_at if present
    created_at = issue_data.get("created_at")
    if created_at:
        properties[NotionProperties.CREATED_AT] = {
            "date": {"start": created_at}
        }

    # Add updated_at if present
    updated_at = issue_data.get("updated_at")
    if updated_at:
        properties[NotionProperties.UPDATED_AT] = {
            "date": {"start": updated_at}
        }

    return properties


def notion_page_to_gitlab_update(page: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Notion page properties to GitLab issue update data.

    Args:
        page: Notion page object containing properties.

    Returns:
        dict[str, Any]: GitLab issue update data containing:
            - title: Issue title
            - description: Issue description
            - state_event: 'close' or 'reopen' if status changed
            - labels: List of label names
    """
    properties = page.get("properties", {})
    update_data: dict[str, Any] = {}

    # Extract title
    title_prop = properties.get(NotionProperties.TITLE, {})
    title_arr = title_prop.get("title", [])
    if title_arr:
        update_data["title"] = title_arr[0].get("text", {}).get("content", "")

    # Extract description
    desc_prop = properties.get(NotionProperties.DESCRIPTION, {})
    desc_arr = desc_prop.get("rich_text", [])
    if desc_arr:
        update_data["description"] = desc_arr[0].get("text", {}).get("content", "")

    # Extract status and convert to state_event
    status_prop = properties.get(NotionProperties.STATUS, {})
    status_select = status_prop.get("select")
    if status_select:
        status_name = status_select.get("name", "")
        notion_status = NOTION_TO_GITLAB_STATUS.get(status_name)
        if notion_status == "closed":
            update_data["state_event"] = "close"
        elif notion_status == "opened":
            update_data["state_event"] = "reopen"

    # Extract labels
    labels_prop = properties.get(NotionProperties.LABELS, {})
    labels_arr = labels_prop.get("multi_select", [])
    if labels_arr:
        update_data["labels"] = [label.get("name") for label in labels_arr if label.get("name")]

    return update_data


def extract_gitlab_iid_from_page(page: dict[str, Any]) -> int | None:
    """
    Extract GitLab IID from Notion page properties.

    Args:
        page: Notion page object.

    Returns:
        int | None: GitLab IID if found, None otherwise.
    """
    properties = page.get("properties", {})
    iid_prop = properties.get(NotionProperties.GITLAB_IID, {})
    return iid_prop.get("number")


def extract_last_synced_from_page(page: dict[str, Any]) -> datetime | None:
    """
    Extract last synced timestamp from Notion page.

    Args:
        page: Notion page object.

    Returns:
        datetime | None: Last synced timestamp if found, None otherwise.
    """
    properties = page.get("properties", {})
    synced_prop = properties.get(NotionProperties.LAST_SYNCED, {})
    date_val = synced_prop.get("date")
    if date_val and date_val.get("start"):
        dt_str = date_val["start"]
        # Ensure timezone info is present
        if "Z" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")
        elif "+" not in dt_str and "-" not in dt_str[10:]:
            # No timezone info, assume UTC
            dt_str = dt_str + "+00:00"
        return datetime.fromisoformat(dt_str)
    return None


def extract_updated_at_from_page(page: dict[str, Any]) -> datetime | None:
    """
    Extract Notion page's last_edited_time.

    Args:
        page: Notion page object.

    Returns:
        datetime | None: Last edited timestamp.
    """
    last_edited = page.get("last_edited_time")
    if last_edited:
        dt_str = last_edited
        # Ensure timezone info is present
        if "Z" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")
        elif "+" not in dt_str and "-" not in dt_str[10:]:
            # No timezone info, assume UTC
            dt_str = dt_str + "+00:00"
        return datetime.fromisoformat(dt_str)
    return None


def extract_title_from_page(page: dict[str, Any]) -> str | None:
    """
    Extract title from Notion page properties.

    Args:
        page: Notion page object.

    Returns:
        str | None: Title string if found, None otherwise.
    """
    properties = page.get("properties", {})
    title_prop = properties.get(NotionProperties.TITLE, {})
    title_arr = title_prop.get("title", [])
    if title_arr:
        return title_arr[0].get("text", {}).get("content", "")
    return None


def extract_description_from_page(page: dict[str, Any]) -> str | None:
    """
    Extract description from Notion page properties.

    Args:
        page: Notion page object.

    Returns:
        str | None: Description string if found, None otherwise.
    """
    properties = page.get("properties", {})
    desc_prop = properties.get(NotionProperties.DESCRIPTION, {})
    desc_arr = desc_prop.get("rich_text", [])
    if desc_arr:
        return desc_arr[0].get("text", {}).get("content", "")
    return None


def extract_labels_from_page(page: dict[str, Any]) -> list[str]:
    """
    Extract labels from Notion page properties.

    Args:
        page: Notion page object.

    Returns:
        list[str]: List of label names.
    """
    properties = page.get("properties", {})
    labels_prop = properties.get(NotionProperties.LABELS, {})
    labels_arr = labels_prop.get("multi_select", [])
    return [label.get("name") for label in labels_arr if label.get("name")]


def notion_page_to_gitlab_create(page: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Notion page to GitLab issue creation data.

    Args:
        page: Notion page object.

    Returns:
        dict[str, Any]: GitLab issue creation data containing:
            - title: Issue title (required)
            - description: Issue description (optional)
            - labels: List of label names (optional)
    """
    create_data: dict[str, Any] = {}

    # Extract title (required)
    title = extract_title_from_page(page)
    if title:
        create_data["title"] = title

    # Extract description (optional)
    description = extract_description_from_page(page)
    if description:
        create_data["description"] = description

    # Extract labels (optional)
    labels = extract_labels_from_page(page)
    if labels:
        create_data["labels"] = labels

    return create_data
