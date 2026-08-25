"""Aggregation helpers for the dashboard's "today" panel.

Everything here is scoped to a single user: CommunicationLog, TaskItem, and
CalendarEvent are all user-owned, so an unscoped query would show one rep
another rep's mail - especially under workspace-wide sync, where every user
in the domain lands in the same database.
"""
import datetime

from django.utils import timezone

from communications.models import CommunicationLog
from gcal.models import CalendarEvent
from gtasks.models import TaskItem

# How far back an urgent message can be and still count as "needs a reply today".
URGENT_MESSAGE_WINDOW_DAYS = 7

# Sort tiers for the action list. Lower runs first.
_TIER_OVERDUE = 0
_TIER_DUE_TODAY = 1
_TIER_URGENT_MESSAGE = 2
_TIER_URGENT_UNDATED = 3


def _day_bounds():
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now, start, start + datetime.timedelta(days=1)


def todays_meetings(user):
    """Today's calendar events for this user, earliest first.

    Declined and cancelled events are already filtered out at sync time.
    """
    if not user or not user.is_authenticated:
        return []

    _, start_of_day, end_of_day = _day_bounds()
    return list(
        CalendarEvent.objects.filter(user=user, start__gte=start_of_day, start__lt=end_of_day)
        .select_related("customer")
        .order_by("start")
    )


def top_actions_today(user, limit=10):
    """The top things this user should actually do today, most pressing first.

    Draws from all three sources, not just tasks:
      1. Overdue open tasks (oldest first)
      2. Tasks due today (earliest first)
      3. Urgent unanswered emails and chat messages (newest first)
      4. Undated tasks flagged urgent

    Meetings are deliberately excluded - they're time-bound commitments
    shown on their own, and letting them compete for the ten action slots
    would push out work that actually needs doing.
    """
    if not user or not user.is_authenticated:
        return []

    now, start_of_day, end_of_day = _day_bounds()
    items = []

    dated_tasks = (
        TaskItem.objects.filter(user=user, due__lt=end_of_day)
        .exclude(status=TaskItem.STATUS_COMPLETED)
        .select_related("customer")
        .order_by("due")[:limit]
    )
    for task in dated_tasks:
        is_overdue = task.due < start_of_day
        items.append(
            {
                "kind": "task",
                "source_label": "Task",
                "title": task.title or "(untitled task)",
                "customer": task.customer,
                "when": task.due,
                "is_overdue": is_overdue,
                "is_urgent": task.is_urgent,
                "detail": (task.notes or "").strip()[:140],
                "_tier": _TIER_OVERDUE if is_overdue else _TIER_DUE_TODAY,
                "_order": task.due,
            }
        )

    urgent_messages = (
        CommunicationLog.objects.filter(
            user=user,
            is_urgent=True,
            occurred_at__gte=now - datetime.timedelta(days=URGENT_MESSAGE_WINDOW_DAYS),
        )
        .select_related("customer")
        .order_by("-occurred_at")[:limit]
    )
    for comm in urgent_messages:
        items.append(
            {
                "kind": comm.source,
                "source_label": "Email" if comm.source == CommunicationLog.SOURCE_EMAIL else "Chat",
                "title": comm.subject or (comm.snippet or "").strip()[:80] or "(no subject)",
                "customer": comm.customer,
                "when": comm.occurred_at,
                "is_overdue": False,
                "is_urgent": True,
                "detail": comm.urgency_reason or (comm.snippet or "").strip()[:140],
                "_tier": _TIER_URGENT_MESSAGE,
                # Newest first within the tier.
                "_order": -comm.occurred_at.timestamp(),
            }
        )

    undated_urgent_tasks = (
        TaskItem.objects.filter(user=user, due__isnull=True, is_urgent=True)
        .exclude(status=TaskItem.STATUS_COMPLETED)
        .select_related("customer")
        .order_by("-updated_at")[:limit]
    )
    for task in undated_urgent_tasks:
        items.append(
            {
                "kind": "task",
                "source_label": "Task",
                "title": task.title or "(untitled task)",
                "customer": task.customer,
                "when": None,
                "is_overdue": False,
                "is_urgent": True,
                "detail": (task.notes or "").strip()[:140],
                "_tier": _TIER_URGENT_UNDATED,
                "_order": -task.updated_at.timestamp(),
            }
        )

    items.sort(key=lambda item: (item["_tier"], item["_order"]))
    return items[:limit]


def urgent_counts(user):
    """Urgent open items for this user, for the header badge."""
    if not user or not user.is_authenticated:
        return 0

    urgent_messages = CommunicationLog.objects.filter(user=user, is_urgent=True).count()
    urgent_tasks = (
        TaskItem.objects.filter(user=user, is_urgent=True)
        .exclude(status=TaskItem.STATUS_COMPLETED)
        .count()
    )
    return urgent_messages + urgent_tasks
