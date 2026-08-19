from django.conf import settings
from django.db import models

from customers.models import Customer


class TaskItem(models.Model):
    """A single Google Tasks item, normalized and linked to a customer."""

    STATUS_NEEDS_ACTION = "needsAction"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_NEEDS_ACTION, "Needs action"),
        (STATUS_COMPLETED, "Completed"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_tasks"
    )
    google_task_id = models.CharField(max_length=255)
    task_list_id = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=1024, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEEDS_ACTION)
    due = models.DateTimeField(null=True, blank=True)
    is_urgent = models.BooleanField(default=False)
    google_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "google_task_id"], name="unique_task_per_user"),
        ]

    def __str__(self):
        return self.title or self.google_task_id
