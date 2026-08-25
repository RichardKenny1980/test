from django.conf import settings
from django.shortcuts import render

from communications.models import Draft
from customers.models import Customer

from .services import top_actions_today, todays_meetings, urgent_counts


def index(request):
    user = request.user
    authenticated = user.is_authenticated

    # Customers are org-level entities, but only surface the ones this user
    # actually has activity with - otherwise every rep sees every account.
    customers = Customer.objects.none()
    drafts = Draft.objects.none()
    if authenticated:
        customers = (
            Customer.objects.filter(communications__user=user)
            .distinct()
            .select_related("summary")
            .prefetch_related("communications", "tasks", "drafts")
            .order_by("name", "company_domain")
        )
        drafts = (
            Draft.objects.filter(status=Draft.STATUS_DRAFT, communication__user=user)
            .select_related("customer")[:10]
        )

    context = {
        "customers": customers,
        "meetings": todays_meetings(user),
        "due_today": top_actions_today(user, limit=10),
        "total_urgent": urgent_counts(user),
        "recent_drafts": drafts,
        "auto_refresh_seconds": settings.DASHBOARD_AUTO_REFRESH_SECONDS,
        "google_connected": authenticated and hasattr(user, "google_credential"),
        "authenticated": authenticated,
    }
    return render(request, "dashboard/index.html", context)
