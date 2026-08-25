"""Aggregation helpers for the dashboard's "due today" panel."""
from django.utils import timezone

from communications.models import CommunicationLog
from gtasks.models import TaskItem


def top_items_due_today(limit=10):
    """The top items needing attention today, most pressing first.

    Ordering: overdue open tasks (oldest due first), then tasks due today,
    then urgent communications from the last 7 days (newest first) to fill
    any remaining slots. Each item is a dict the template can render
    directly.
    """
    now = timezone.localtime()
    today = now.date()
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    items = []

    open_tasks = (
        TaskItem.objects.filter(due__lte=end_of_today)
        .exclude(status=TaskItem.STATUS_COMPLETED)
        .select_related("customer")
        .order_by("due")[:limit]
    )
    for task in open_tasks:
        due_date = timezone.localtime(task.due).date()
        items.append(
            {
                "kind": "task",
                "title": task.title or "(untitled task)",
                "customer": task.customer,
                "when": task.due,
                "is_overdue": due_date < today,
                "is_urgent": task.is_urgent,
                "detail": (task.notes or "")[:140],
            }
        )

    if len(items) < limit:
        urgent_comms = (
            CommunicationLog.objects.filter(
                is_urgent=True, occurred_at__gte=now - timezone.timedelta(days=7)
            )
            .select_related("customer")
            .order_by("-occurred_at")[: limit - len(items)]
        )
        for comm in urgent_comms:
            items.append(
                {
                    "kind": comm.source,
                    "title": comm.subject or (comm.snippet[:80] if comm.snippet else "(no subject)"),
                    "customer": comm.customer,
                    "when": comm.occurred_at,
                    "is_overdue": False,
                    "is_urgent": True,
                    "detail": comm.urgency_reason or (comm.snippet or "")[:140],
                }
            )

    return items[:limit]
