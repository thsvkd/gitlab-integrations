"""
Synchronization logic between GitLab and Notion.

This module provides functions for bidirectional sync between
GitLab issues and Notion database pages.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from gitlab_integrations.config import settings
from gitlab_integrations.gitlab import api as gitlab_api
from gitlab_integrations.notion.api import NotionClient, get_notion_client
from gitlab_integrations.notion.schemas import (
    NotionProperties,
    extract_gitlab_iid_from_page,
    extract_last_synced_from_page,
    extract_title_from_page,
    extract_updated_at_from_page,
    gitlab_issue_to_notion_properties,
    notion_page_to_gitlab_update,
)

logger = logging.getLogger(__name__)


def sync_gitlab_to_notion(
    issue_data: dict[str, Any],
    client: NotionClient | None = None,
) -> dict[str, Any] | None:
    """
    Sync a GitLab issue to Notion.

    Creates a new Notion page if it doesn't exist, or updates
    the existing page if found.

    Args:
        issue_data: GitLab issue data (from webhook or API).
        client: Optional NotionClient instance. Uses global client if None.

    Returns:
        dict[str, Any] | None: Created/updated Notion page, or None if sync disabled.
    """
    if not settings.notion_sync_enabled:
        logger.debug("Notion sync is disabled")
        return None

    client = client or get_notion_client()
    gitlab_iid = issue_data.get("iid")

    if not gitlab_iid:
        logger.warning("Cannot sync issue without IID")
        return None

    logger.info(f"Syncing GitLab issue #{gitlab_iid} to Notion")

    # Convert GitLab issue to Notion properties
    properties = gitlab_issue_to_notion_properties(issue_data)

    # Check if page already exists
    existing_page = client.get_page_by_gitlab_iid(gitlab_iid)

    if existing_page:
        # Update existing page
        page_id = existing_page["id"]
        logger.info(f"Updating existing Notion page {page_id} for issue #{gitlab_iid}")
        return client.update_page(page_id, properties)
    else:
        # Create new page
        logger.info(f"Creating new Notion page for issue #{gitlab_iid}")
        return client.create_page(properties)


def sync_notion_to_gitlab(
    page: dict[str, Any],
    client: NotionClient | None = None,
) -> bool:
    """
    Sync a Notion page to GitLab.

    Updates the corresponding GitLab issue based on Notion page changes.

    Args:
        page: Notion page object.
        client: Optional NotionClient instance. Uses global client if None.

    Returns:
        bool: True if sync was successful, False otherwise.
    """
    if not settings.notion_sync_enabled:
        logger.debug("Notion sync is disabled")
        return False

    client = client or get_notion_client()

    gitlab_iid = extract_gitlab_iid_from_page(page)
    if not gitlab_iid:
        logger.warning(f"Page {page.get('id')} has no GitLab IID, skipping")
        return False

    logger.info(f"Syncing Notion page to GitLab issue #{gitlab_iid}")

    # Get current GitLab issue
    gitlab_issue = gitlab_api.get_issue_by_iid(gitlab_iid)
    if not gitlab_issue:
        logger.warning(f"GitLab issue #{gitlab_iid} not found")
        return False

    # Convert Notion page to GitLab update data
    update_data = notion_page_to_gitlab_update(page)

    if not update_data:
        logger.debug(f"No changes to sync for issue #{gitlab_iid}")
        return True

    try:
        # Apply updates to GitLab issue
        project = gitlab_api.get_project()
        issue = project.issues.get(gitlab_iid)

        # Update title if changed
        if "title" in update_data and update_data["title"] != issue.title:
            issue.title = update_data["title"]

        # Update description if changed
        if "description" in update_data and update_data["description"] != (issue.description or ""):
            issue.description = update_data["description"]

        # Update labels if changed
        if "labels" in update_data:
            issue.labels = update_data["labels"]

        # Save changes
        issue.save()

        # Handle state change separately (close/reopen)
        if "state_event" in update_data:
            state_event = update_data["state_event"]
            current_state = issue.state
            if state_event == "close" and current_state != "closed":
                gitlab_api.update_issue_state(gitlab_iid, "close")
            elif state_event == "reopen" and current_state != "opened":
                gitlab_api.update_issue_state(gitlab_iid, "reopen")

        # Update Last Synced in Notion
        page_id = page["id"]
        client.update_page(page_id, {
            NotionProperties.LAST_SYNCED: {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            }
        })

        logger.info(f"Successfully synced Notion page to GitLab issue #{gitlab_iid}")
        return True

    except Exception as e:
        logger.error(f"Failed to sync Notion page to GitLab issue #{gitlab_iid}: {e}")
        return False


def check_conflict(
    page: dict[str, Any],
    gitlab_issue: Any,
) -> tuple[bool, str | None]:
    """
    Check for sync conflicts between Notion page and GitLab issue.

    A conflict occurs when both sides have been modified since the last sync.

    Args:
        page: Notion page object.
        gitlab_issue: GitLab issue object.

    Returns:
        tuple[bool, str | None]: (has_conflict, winner) where winner is
            'notion' or 'gitlab' if using LWW, or None if no conflict.
    """
    last_synced = extract_last_synced_from_page(page)
    notion_updated = extract_updated_at_from_page(page)

    # Get GitLab updated_at
    gitlab_updated_str = getattr(gitlab_issue, "updated_at", None)
    gitlab_updated = None
    if gitlab_updated_str:
        gitlab_updated = datetime.fromisoformat(gitlab_updated_str.replace("Z", "+00:00"))

    # If no last_synced, this is a new sync - no conflict
    if not last_synced:
        return (False, None)

    # Check if both sides modified since last sync
    notion_modified = notion_updated and notion_updated > last_synced
    gitlab_modified = gitlab_updated and gitlab_updated > last_synced

    if notion_modified and gitlab_modified:
        # Conflict! Use LWW to resolve
        winner = resolve_conflict_lww(notion_updated, gitlab_updated)
        return (True, winner)

    return (False, None)


def resolve_conflict_lww(
    notion_updated: datetime | None,
    gitlab_updated: datetime | None,
) -> str:
    """
    Resolve conflict using Last Write Wins (LWW) strategy.

    Args:
        notion_updated: Notion page last edited time.
        gitlab_updated: GitLab issue updated_at time.

    Returns:
        str: 'notion' or 'gitlab' indicating which side wins.
    """
    if notion_updated is None:
        return "gitlab"
    if gitlab_updated is None:
        return "notion"

    if notion_updated > gitlab_updated:
        return "notion"
    return "gitlab"


def sync_modified_notion_pages(
    since: str | None = None,
    client: NotionClient | None = None,
) -> dict[str, int]:
    """
    Sync all modified Notion pages to GitLab.

    This is the main entry point for polling-based Notion → GitLab sync.

    Args:
        since: ISO timestamp to filter pages modified after this time.
        client: Optional NotionClient instance.

    Returns:
        dict[str, int]: Sync statistics with keys:
            - total: Total pages processed
            - synced: Successfully synced
            - skipped: Skipped (no changes or conflict lost)
            - failed: Failed to sync
    """
    if not settings.notion_sync_enabled:
        return {"total": 0, "synced": 0, "skipped": 0, "failed": 0}

    client = client or get_notion_client()
    stats = {"total": 0, "synced": 0, "skipped": 0, "failed": 0}

    try:
        pages = client.query_modified_pages(since=since)
        stats["total"] = len(pages)

        for page in pages:
            gitlab_iid = extract_gitlab_iid_from_page(page)
            if not gitlab_iid:
                stats["skipped"] += 1
                continue

            # Get GitLab issue for conflict check
            gitlab_issue = gitlab_api.get_issue_by_iid(gitlab_iid)
            if not gitlab_issue:
                logger.warning(f"GitLab issue #{gitlab_iid} not found, skipping")
                stats["skipped"] += 1
                continue

            # Check for conflicts
            has_conflict, winner = check_conflict(page, gitlab_issue)
            if has_conflict:
                logger.info(f"Conflict detected for issue #{gitlab_iid}, winner: {winner}")
                if winner == "gitlab":
                    # GitLab wins - sync GitLab to Notion instead
                    issue_data = {
                        "iid": gitlab_issue.iid,
                        "title": gitlab_issue.title,
                        "description": gitlab_issue.description,
                        "state": gitlab_issue.state,
                        "labels": gitlab_issue.labels,
                        "web_url": gitlab_issue.web_url,
                        "updated_at": gitlab_issue.updated_at,
                    }
                    sync_gitlab_to_notion(issue_data, client)
                    stats["skipped"] += 1
                    continue

            # Notion wins or no conflict - sync Notion to GitLab
            if sync_notion_to_gitlab(page, client):
                stats["synced"] += 1
            else:
                stats["failed"] += 1

    except Exception as e:
        logger.error(f"Error during Notion sync: {e}")

    logger.info(f"Notion sync complete: {stats}")
    return stats


def full_reconciliation_sync(
    client: NotionClient | None = None,
) -> dict[str, Any]:
    """
    Perform full reconciliation sync between GitLab and Notion.

    This function:
    1. Fetches all GitLab issues
    2. Fetches all Notion pages
    3. Matches by GitLab IID
    4. Compares timestamps and syncs using LWW (Last Write Wins)
    5. Creates Notion pages for GitLab issues that don't exist in Notion

    Args:
        client: Optional NotionClient instance. Uses global client if None.

    Returns:
        dict[str, Any]: Sync statistics with keys:
            - gitlab_total: Total GitLab issues
            - notion_total: Total Notion pages
            - created_in_notion: Pages created in Notion
            - updated_in_notion: Pages updated in Notion
            - updated_in_gitlab: Issues updated in GitLab
            - skipped: Items skipped (no changes needed)
            - failed: Failed sync operations
    """
    if not settings.notion_sync_enabled:
        logger.info("Notion sync is disabled")
        return {
            "gitlab_total": 0,
            "notion_total": 0,
            "created_in_notion": 0,
            "updated_in_notion": 0,
            "updated_in_gitlab": 0,
            "skipped": 0,
            "failed": 0,
        }

    client = client or get_notion_client()
    stats = {
        "gitlab_total": 0,
        "notion_total": 0,
        "created_in_notion": 0,
        "updated_in_notion": 0,
        "updated_in_gitlab": 0,
        "skipped": 0,
        "failed": 0,
    }

    logger.info("Starting full reconciliation sync...")

    try:
        # 1. Fetch all GitLab issues
        logger.info("Fetching all GitLab issues...")
        gitlab_issues = gitlab_api.list_all_issues(state="all")
        stats["gitlab_total"] = len(gitlab_issues)
        logger.info(f"Found {len(gitlab_issues)} GitLab issues")

        # Build GitLab issues map by IID
        gitlab_by_iid: dict[int, Any] = {issue.iid: issue for issue in gitlab_issues}

        # 2. Fetch all Notion pages
        logger.info("Fetching all Notion pages...")
        notion_pages = client.query_database_all()
        stats["notion_total"] = len(notion_pages)
        logger.info(f"Found {len(notion_pages)} Notion pages")

        # Build Notion pages map by GitLab IID
        notion_by_iid: dict[int, dict[str, Any]] = {}
        notion_without_iid: list[dict[str, Any]] = []

        for page in notion_pages:
            gitlab_iid = extract_gitlab_iid_from_page(page)
            if gitlab_iid:
                notion_by_iid[gitlab_iid] = page
            else:
                notion_without_iid.append(page)

        # 3. Process GitLab issues
        for iid, gitlab_issue in gitlab_by_iid.items():
            notion_page = notion_by_iid.get(iid)

            if notion_page:
                # Both exist - compare timestamps and use LWW
                result = _reconcile_existing(gitlab_issue, notion_page, client)
                if result == "updated_notion":
                    stats["updated_in_notion"] += 1
                elif result == "updated_gitlab":
                    stats["updated_in_gitlab"] += 1
                elif result == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["failed"] += 1
            else:
                # GitLab only - create in Notion
                result = _create_notion_from_gitlab(gitlab_issue, client)
                if result:
                    stats["created_in_notion"] += 1
                else:
                    stats["failed"] += 1

        # 4. Skip Notion pages without GitLab IID (they need manual button click)
        stats["skipped"] += len(notion_without_iid)
        if notion_without_iid:
            logger.info(
                f"Skipped {len(notion_without_iid)} Notion pages without GitLab IID "
                "(use 'Push to GitLab' button to sync)"
            )

    except Exception as e:
        logger.error(f"Error during full reconciliation sync: {e}")

    logger.info(f"Full reconciliation sync complete: {stats}")
    return stats


def _reconcile_existing(
    gitlab_issue: Any,
    notion_page: dict[str, Any],
    client: NotionClient,
) -> str:
    """
    Reconcile an existing GitLab issue and Notion page.

    Compares timestamps and syncs in the direction of the newer change.

    Args:
        gitlab_issue: GitLab issue object.
        notion_page: Notion page object.
        client: NotionClient instance.

    Returns:
        str: Result status - 'updated_notion', 'updated_gitlab', 'skipped', or 'failed'.
    """
    gitlab_iid = gitlab_issue.iid

    # Get timestamps
    gitlab_updated_str = getattr(gitlab_issue, "updated_at", None)
    gitlab_updated = None
    if gitlab_updated_str:
        gitlab_updated = datetime.fromisoformat(gitlab_updated_str.replace("Z", "+00:00"))

    notion_updated = extract_updated_at_from_page(notion_page)
    last_synced = extract_last_synced_from_page(notion_page)

    # Determine sync direction using LWW
    if gitlab_updated and notion_updated:
        if gitlab_updated > notion_updated:
            # GitLab is newer - update Notion
            logger.debug(f"Issue #{gitlab_iid}: GitLab is newer, updating Notion")
            issue_data = {
                "iid": gitlab_issue.iid,
                "title": gitlab_issue.title,
                "description": gitlab_issue.description,
                "state": gitlab_issue.state,
                "labels": gitlab_issue.labels,
                "web_url": gitlab_issue.web_url,
                "updated_at": gitlab_issue.updated_at,
                "author": getattr(gitlab_issue, "author", None),
                "created_at": getattr(gitlab_issue, "created_at", None),
            }
            try:
                sync_gitlab_to_notion(issue_data, client)
                return "updated_notion"
            except Exception as e:
                logger.error(f"Failed to update Notion for issue #{gitlab_iid}: {e}")
                return "failed"
        elif notion_updated > gitlab_updated:
            # Notion is newer - check if it was modified after last sync
            if last_synced and notion_updated > last_synced:
                logger.debug(f"Issue #{gitlab_iid}: Notion is newer, updating GitLab")
                try:
                    if sync_notion_to_gitlab(notion_page, client):
                        return "updated_gitlab"
                    return "failed"
                except Exception as e:
                    logger.error(f"Failed to update GitLab for issue #{gitlab_iid}: {e}")
                    return "failed"
            else:
                logger.debug(f"Issue #{gitlab_iid}: Notion newer but not modified since sync, skipping")
                return "skipped"
        else:
            # Same timestamp - skip
            logger.debug(f"Issue #{gitlab_iid}: Same timestamp, skipping")
            return "skipped"
    elif gitlab_updated:
        # Only GitLab has timestamp - update Notion
        logger.debug(f"Issue #{gitlab_iid}: Only GitLab has timestamp, updating Notion")
        issue_data = {
            "iid": gitlab_issue.iid,
            "title": gitlab_issue.title,
            "description": gitlab_issue.description,
            "state": gitlab_issue.state,
            "labels": gitlab_issue.labels,
            "web_url": gitlab_issue.web_url,
            "updated_at": gitlab_issue.updated_at,
            "author": getattr(gitlab_issue, "author", None),
            "created_at": getattr(gitlab_issue, "created_at", None),
        }
        try:
            sync_gitlab_to_notion(issue_data, client)
            return "updated_notion"
        except Exception as e:
            logger.error(f"Failed to update Notion for issue #{gitlab_iid}: {e}")
            return "failed"
    else:
        # No timestamps available - skip
        logger.debug(f"Issue #{gitlab_iid}: No timestamps available, skipping")
        return "skipped"


def _create_notion_from_gitlab(
    gitlab_issue: Any,
    client: NotionClient,
) -> bool:
    """
    Create a Notion page from a GitLab issue.

    Args:
        gitlab_issue: GitLab issue object.
        client: NotionClient instance.

    Returns:
        bool: True if creation was successful, False otherwise.
    """
    gitlab_iid = gitlab_issue.iid
    logger.info(f"Creating Notion page for GitLab issue #{gitlab_iid}")

    issue_data = {
        "iid": gitlab_issue.iid,
        "title": gitlab_issue.title,
        "description": gitlab_issue.description,
        "state": gitlab_issue.state,
        "labels": gitlab_issue.labels,
        "web_url": gitlab_issue.web_url,
        "updated_at": getattr(gitlab_issue, "updated_at", None),
        "author": getattr(gitlab_issue, "author", None),
        "created_at": getattr(gitlab_issue, "created_at", None),
    }

    try:
        result = sync_gitlab_to_notion(issue_data, client)
        if result:
            # Update sync status
            page_id = result.get("id")
            if page_id:
                client.update_sync_status(
                    page_id=page_id,
                    synced=True,
                    sync_error=None,
                )
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to create Notion page for issue #{gitlab_iid}: {e}")
        return False
