"""
Notion integration module for GitLab-Notion bidirectional sync.

This module provides functionality to synchronize GitLab issues with Notion databases.
"""

from gitlab_integrations.notion.api import NotionClient
from gitlab_integrations.notion.sync import sync_gitlab_to_notion, sync_notion_to_gitlab

__all__ = [
    "NotionClient",
    "sync_gitlab_to_notion",
    "sync_notion_to_gitlab",
]
