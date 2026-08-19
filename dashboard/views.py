from django.conf import settings
from django.shortcuts import render

from communications.models import CommunicationLog, Draft
from customers.models import Customer
from gtasks.models import TaskItem


def index(request):
    customers = (
        Customer.objects.all()
        .select_related("summary")
        .prefetch_related("communications", "tasks", "drafts")
        .order_by("name", "company_domain")
    )

    urgent_comm_count = CommunicationLog.objects.filter(is_urgent=True).count()
    urgent_task_count = TaskItem.objects.filter(is_urgent=True).exclude(
        status=TaskItem.STATUS_COMPLETED
    ).count()

    context = {
        "customers": customers,
        "total_urgent": urgent_comm_count + urgent_task_count,
        "recent_drafts": Draft.objects.filter(status=Draft.STATUS_DRAFT).select_related("customer")[:10],
        "auto_refresh_seconds": settings.DASHBOARD_AUTO_REFRESH_SECONDS,
        "google_connected": request.user.is_authenticated
        and hasattr(request.user, "google_credential"),
    }
    return render(request, "dashboard/index.html", context)
