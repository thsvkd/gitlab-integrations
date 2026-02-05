"""
Background tasks for GitLab-Notion synchronization.

This module provides scheduled tasks for full reconciliation sync
between GitLab and Notion using APScheduler.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from gitlab_integrations.config import settings
from gitlab_integrations.notion.sync import full_reconciliation_sync

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None

def run_full_sync() -> None:
    """
    Run full reconciliation sync between GitLab and Notion.

    This function is called at startup and periodically by the scheduler
    to keep GitLab and Notion in sync.
    """
    if not settings.notion_sync_enabled:
        logger.debug("Notion sync is disabled, skipping")
        return

    logger.info("Running full reconciliation sync...")

    try:
        stats = full_reconciliation_sync()
        logger.info(
            f"Full sync complete - "
            f"GitLab: {stats['gitlab_total']}, Notion: {stats['notion_total']}, "
            f"created: {stats['created_in_notion']}, updated_notion: {stats['updated_in_notion']}, "
            f"updated_gitlab: {stats['updated_in_gitlab']}, skipped: {stats['skipped']}, "
            f"failed: {stats['failed']}"
        )
    except Exception as e:
        logger.error(f"Error during full sync: {e}")


def start_polling_scheduler() -> BackgroundScheduler | None:
    """
    Start the Notion sync scheduler.

    Creates and starts a background scheduler that runs full reconciliation
    at the configured interval. Also runs an initial sync at startup.

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

    # Run initial full sync at startup
    logger.info("Running initial full sync at startup...")
    run_full_sync()

    interval_seconds = settings.notion_sync_interval
    logger.info(f"Starting Notion sync scheduler (interval: {interval_seconds}s)")

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_full_sync,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id="notion_full_sync",
        name="Full reconciliation sync",
        replace_existing=True,
    )
    _scheduler.start()

    logger.info("Notion sync scheduler started")
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
