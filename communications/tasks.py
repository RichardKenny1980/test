"""Celery tasks that pull Gmail/Chat data in the background and fan out to
customer grouping, urgency flagging, and summarization.
"""
import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from accounts import workspace
from accounts.services import get_gmail_chat_credentials
from customers.utils import get_or_create_customer_for_email

from . import summarizer
from .models import CommunicationLog
from .services.chat import fetch_recent_space_messages
from .services.gmail import fetch_recent_messages

logger = logging.getLogger(__name__)
User = get_user_model()


def _users_with_google_credentials():
    return User.objects.filter(google_credential__isnull=False)


def _upsert_communication(user, source, message):
    customer = None
    if message["sender_email"]:
        customer = get_or_create_customer_for_email(message["sender_email"])

    comm, _ = CommunicationLog.objects.update_or_create(
        user=user,
        source=source,
        external_id=message["external_id"],
        defaults={
            "customer": customer,
            "thread_id": message["thread_id"],
            "sender_email": message["sender_email"],
            "sender_name": message["sender_name"],
            "subject": message["subject"],
            "snippet": message["snippet"],
            "body_text": message["body_text"],
            "occurred_at": message["occurred_at"],
            "raw_payload": message["raw_payload"],
        },
    )
    summarizer.flag_communication(comm)
    return comm


@shared_task
def sync_gmail_for_user(user_id):
    user = User.objects.get(pk=user_id)
    credentials = get_gmail_chat_credentials(user)
    if not credentials:
        logger.info("No Google credentials for user %s; skipping Gmail sync", user_id)
        return 0

    count = 0
    for message in fetch_recent_messages(credentials):
        comm = _upsert_communication(user, CommunicationLog.SOURCE_EMAIL, message)
        if comm.customer:
            summarizer.build_customer_summary(comm.customer)
            if comm.is_urgent:
                summarizer.generate_draft_reply(comm)
        count += 1
    return count


@shared_task
def sync_chat_for_user(user_id):
    user = User.objects.get(pk=user_id)
    credentials = get_gmail_chat_credentials(user)
    if not credentials:
        logger.info("No Google credentials for user %s; skipping Chat sync", user_id)
        return 0

    count = 0
    for message in fetch_recent_space_messages(credentials):
        comm = _upsert_communication(user, CommunicationLog.SOURCE_CHAT, message)
        if comm.customer:
            summarizer.build_customer_summary(comm.customer)
        count += 1
    return count


@shared_task
def sync_all_communications():
    """Fan out Gmail/Chat sync for individually-connected users.

    When workspace-wide domain delegation is enabled, accounts.tasks.
    sync_workspace_directory already discovers and syncs every user in the
    domain for Gmail/Chat, so this is skipped to avoid duplicate API calls.
    """
    if workspace.is_enabled():
        return

    for user in _users_with_google_credentials():
        sync_gmail_for_user.delay(user.id)
        sync_chat_for_user.delay(user.id)


@shared_task
def refresh_all_customer_summaries():
    from customers.models import Customer

    for customer in Customer.objects.all():
        summarizer.build_customer_summary(customer)
