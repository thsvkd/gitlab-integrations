"""
Background polling tasks for Notion synchronization.

This module provides scheduled tasks for polling Notion changes
and syncing them to GitLab using APScheduler.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from gitlab_integrations.config import settings
from gitlab_integrations.notion.sync import sync_modified_notion_pages

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None

# Track last poll time
_last_poll_time: datetime | None = None


def poll_notion_changes() -> None:
    """
    Poll Notion for changes and sync to GitLab.

    This function is called periodically by the scheduler to check
    for Notion page modifications and sync them to GitLab.
    """
    global _last_poll_time

    if not settings.notion_sync_enabled:
        logger.debug("Notion sync is disabled, skipping poll")
        return

    logger.info("Polling Notion for changes...")

    # Use last poll time, or look back 5 minutes on first run
    since = None
    if _last_poll_time:
        since = _last_poll_time.isoformat()
    else:
        # First run: look back a bit to catch recent changes
        since = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

    # Update last poll time before sync (in case of long sync)
    _last_poll_time = datetime.utcnow()

    try:
        stats = sync_modified_notion_pages(since=since)
        logger.info(
            f"Notion poll complete - "
            f"total: {stats['total']}, synced: {stats['synced']}, "
            f"skipped: {stats['skipped']}, failed: {stats['failed']}"
        )
    except Exception as e:
        logger.error(f"Error during Notion poll: {e}")


def start_polling_scheduler() -> BackgroundScheduler | None:
    """
    Start the Notion polling scheduler.

    Creates and starts a background scheduler that polls Notion
    at the configured interval.

    Returns:
        BackgroundScheduler | None: Started scheduler instance,
            or None if sync is disabled.
    """
    global _scheduler

    if not settings.notion_sync_enabled:
        logger.info("Notion sync is disabled, not starting scheduler")
        return None

    if not settings.notion_token or not settings.notion_database_id:
        logger.warning(
            "Notion token or database ID not configured, not starting scheduler"
        )
        return None

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler is already running")
        return _scheduler

    interval_seconds = settings.notion_sync_interval
    logger.info(f"Starting Notion polling scheduler (interval: {interval_seconds}s)")

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        poll_notion_changes,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id="notion_poll",
        name="Poll Notion for changes",
        replace_existing=True,
    )
    _scheduler.start()

    logger.info("Notion polling scheduler started")
    return _scheduler


def stop_polling_scheduler() -> None:
    """
    Stop the Notion polling scheduler.

    Gracefully shuts down the scheduler if it's running.
    """
    global _scheduler

    if _scheduler is None:
        logger.debug("Scheduler is not initialized")
        return

    if not _scheduler.running:
        logger.debug("Scheduler is not running")
        return

    logger.info("Stopping Notion polling scheduler...")
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Notion polling scheduler stopped")


def get_scheduler() -> BackgroundScheduler | None:
    """
    Get the current scheduler instance.

    Returns:
        BackgroundScheduler | None: Current scheduler instance or None.
    """
    return _scheduler


def is_scheduler_running() -> bool:
    """
    Check if the scheduler is currently running.

    Returns:
        bool: True if scheduler is running, False otherwise.
    """
    return _scheduler is not None and _scheduler.running
