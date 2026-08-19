"""Celery tasks that pull Google Tasks data in the background."""
import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from accounts.services import get_credentials
from communications import summarizer
from customers.utils import find_customer_by_text

from .models import TaskItem
from .services import fetch_all_tasks

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def sync_tasks_for_user(user_id):
    user = User.objects.get(pk=user_id)
    credentials = get_credentials(user)
    if not credentials:
        logger.info("No Google credentials for user %s; skipping Tasks sync", user_id)
        return 0

    count = 0
    touched_customer_ids = set()
    for task in fetch_all_tasks(credentials):
        item, _ = TaskItem.objects.update_or_create(
            user=user,
            google_task_id=task["google_task_id"],
            defaults={
                "task_list_id": task["task_list_id"],
                "title": task["title"],
                "notes": task["notes"],
                "status": task["status"],
                "due": task["due"],
                "google_updated_at": task["google_updated_at"],
            },
        )

        # Google Tasks have no structured contact field, so best-effort match a
        # customer mentioned by email address in the title/notes.
        customer = find_customer_by_text(f"{item.title} {item.notes}")
        if customer and item.customer_id != customer.id:
            item.customer = customer
            item.save(update_fields=["customer"])

        summarizer.flag_task(item)
        if item.customer_id:
            touched_customer_ids.add(item.customer_id)
        count += 1

    if touched_customer_ids:
        from customers.models import Customer

        for customer in Customer.objects.filter(id__in=touched_customer_ids):
            summarizer.build_customer_summary(customer)

    return count


@shared_task
def sync_all_tasks():
    for user in User.objects.filter(google_credential__isnull=False):
        sync_tasks_for_user.delay(user.id)
