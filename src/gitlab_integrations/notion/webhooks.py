"""
Notion webhook handlers for button actions.

This module provides FastAPI endpoints for handling Notion button clicks,
specifically the "Push to GitLab" button that creates GitLab issues from
Notion pages.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from gitlab_integrations.config import settings
from gitlab_integrations.gitlab import api as gitlab_api
from gitlab_integrations.notion.api import get_notion_client
from gitlab_integrations.notion.schemas import (
    extract_gitlab_iid_from_page,
    extract_title_from_page,
    notion_page_to_gitlab_create,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def notion_button_webhook(request: Request) -> dict[str, Any]:
    """
    Handle Notion button webhook (Push to GitLab).

    This endpoint is called when a user clicks the "Push to GitLab" button
    in Notion. It creates a new GitLab issue from the Notion page data.

    Expected payload format from Notion button:
    {
        "source": {
            "type": "automation",
            "automation_id": "...",
            ...
        },
        "data": {
            "page_id": "...",
            "properties": {
                "Title": {"title": [{"text": {"content": "..."}}]},
                "Description": {"rich_text": [{"text": {"content": "..."}}]},
                "Labels": {"multi_select": [{"name": "..."}]}
            }
        }
    }

    Returns:
        dict[str, Any]: Response with status and created issue info.

    Raises:
        HTTPException: If validation fails or GitLab API error occurs.
    """
    if not settings.notion_sync_enabled:
        raise HTTPException(status_code=503, detail="Notion sync is disabled")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(f"Received Notion button webhook: {payload}")

    # Extract page data from payload
    data = payload.get("data", {})
    page_id = data.get("page_id")

    if not page_id:
        logger.error("No page_id in webhook payload")
        raise HTTPException(status_code=400, detail="Missing page_id in payload")

    notion_client = get_notion_client()

    # Fetch the full page to get all properties
    try:
        page = notion_client.get_page(page_id)
    except Exception as e:
        logger.error(f"Failed to fetch Notion page {page_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Page not found: {page_id}")

    # Check if already synced (has GitLab IID)
    existing_iid = extract_gitlab_iid_from_page(page)
    if existing_iid:
        logger.info(f"Page {page_id} already synced to GitLab issue #{existing_iid}")
        notion_client.update_sync_status(
            page_id=page_id,
            synced=True,
            sync_error=None,
            gitlab_iid=existing_iid,
        )
        return {
            "status": "already_synced",
            "message": f"Page already linked to GitLab issue #{existing_iid}",
            "gitlab_iid": existing_iid,
        }

    # Extract title (required)
    title = extract_title_from_page(page)
    if not title or not title.strip():
        error_msg = "Title is required to create a GitLab issue"
        logger.warning(f"Page {page_id} missing title")
        notion_client.update_sync_status(
            page_id=page_id,
            synced=False,
            sync_error=error_msg,
        )
        return {
            "status": "error",
            "message": error_msg,
        }

    # Convert Notion page to GitLab issue data
    create_data = notion_page_to_gitlab_create(page)

    # Create GitLab issue
    try:
        issue = gitlab_api.create_issue(
            title=create_data.get("title", ""),
            description=create_data.get("description", ""),
            labels=create_data.get("labels"),
        )

        gitlab_iid = issue.iid
        gitlab_url = issue.web_url

        logger.info(f"Created GitLab issue #{gitlab_iid} from Notion page {page_id}")

        # Update Notion page with sync status
        notion_client.update_sync_status(
            page_id=page_id,
            synced=True,
            sync_error=None,
            gitlab_iid=gitlab_iid,
            gitlab_url=gitlab_url,
        )

        return {
            "status": "success",
            "message": f"Created GitLab issue #{gitlab_iid}",
            "gitlab_iid": gitlab_iid,
            "gitlab_url": gitlab_url,
        }

    except Exception as e:
        error_msg = f"Failed to create GitLab issue: {str(e)}"
        logger.error(f"Error creating GitLab issue from page {page_id}: {e}")

        # Update Notion page with error
        try:
            notion_client.update_sync_status(
                page_id=page_id,
                synced=False,
                sync_error=error_msg,
            )
        except Exception as update_error:
            logger.error(f"Failed to update sync status: {update_error}")

        return {
            "status": "error",
            "message": error_msg,
        }
