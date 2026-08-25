"""Celery tasks that pull Google Calendar events in the background."""
import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from accounts.services import get_gmail_chat_credentials
from customers.utils import get_or_create_customer_for_email

from .models import CalendarEvent
from .services import fetch_events

logger = logging.getLogger(__name__)
User = get_user_model()


def _match_customer(user, attendees):
    """Link an event to the customer of its first external attendee.

    Internal colleagues aren't customers, so anyone sharing the organiser's
    email domain is skipped.
    """
    own_domain = (user.email or "").rsplit("@", 1)[-1].lower()

    for attendee in attendees:
        email = (attendee.get("email") or "").strip().lower()
        if not email or email == (user.email or "").lower():
            continue
        if own_domain and email.endswith(f"@{own_domain}"):
            continue
        customer = get_or_create_customer_for_email(email, name=attendee.get("name", ""))
        if customer:
            return customer
    return None


@shared_task
def sync_calendar_for_user(user_id):
    user = User.objects.get(pk=user_id)
    credentials = get_gmail_chat_credentials(user)
    if not credentials:
        logger.info("No Google credentials for user %s; skipping Calendar sync", user_id)
        return 0

    count = 0
    for event in fetch_events(credentials):
        customer = _match_customer(user, event["attendees"])
        CalendarEvent.objects.update_or_create(
            user=user,
            google_event_id=event["google_event_id"],
            defaults={
                "customer": customer,
                "calendar_id": event["calendar_id"],
                "title": event["title"],
                "description": event["description"],
                "location": event["location"],
                "conference_url": event["conference_url"],
                "start": event["start"],
                "end": event["end"],
                "is_all_day": event["is_all_day"],
                "attendees": event["attendees"],
                "organizer_email": event["organizer_email"],
            },
        )
        count += 1
    return count


@shared_task
def sync_all_calendars():
    from accounts import workspace

    if workspace.is_enabled():
        # Workspace directory sync fans out per-user calendar syncs itself.
        return

    for user in User.objects.filter(google_credential__isnull=False):
        sync_calendar_for_user.delay(user.id)
