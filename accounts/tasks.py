"""Celery task that discovers every active Workspace user via domain-wide
delegation and fans out Gmail/Chat sync for each of them.
"""
import logging

from celery import shared_task

from . import workspace
from .services import get_or_create_local_user

logger = logging.getLogger(__name__)


@shared_task
def sync_workspace_directory():
    """List every active user in the delegated Workspace domain and kick off
    a Gmail + Chat sync for each. Google Tasks isn't covered - it has no
    domain-wide-delegation support, so gtasks.tasks.sync_all_tasks (the
    per-user OAuth path) still owns Tasks regardless of this task.
    """
    if not workspace.is_enabled():
        logger.info("Workspace-wide sync is not configured; skipping directory sync")
        return 0

    from communications.tasks import sync_chat_for_user, sync_gmail_for_user

    count = 0
    for email in workspace.list_workspace_user_emails():
        user = get_or_create_local_user(email)
        sync_gmail_for_user.delay(user.id)
        sync_chat_for_user.delay(user.id)
        count += 1
    return count
