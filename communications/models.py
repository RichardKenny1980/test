from django.conf import settings
from django.db import models

from customers.models import Customer


class CommunicationLog(models.Model):
    """A single Gmail message or Google Chat/Spaces message, normalized."""

    SOURCE_EMAIL = "email"
    SOURCE_CHAT = "chat"
    SOURCE_CHOICES = [
        (SOURCE_EMAIL, "Gmail"),
        (SOURCE_CHAT, "Google Chat / Spaces"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="communications"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="communications"
    )
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    external_id = models.CharField(max_length=255)
    thread_id = models.CharField(max_length=255, blank=True)
    sender_email = models.EmailField(blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=998, blank=True)
    snippet = models.TextField(blank=True)
    body_text = models.TextField(blank=True)
    is_urgent = models.BooleanField(default=False)
    urgency_reason = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField()
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source", "external_id"], name="unique_comm_per_user_source"
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "-occurred_at"]),
        ]

    def __str__(self):
        return f"[{self.source}] {self.subject or self.snippet[:40]}"


class CustomerSummary(models.Model):
    """Cached summary shown on the dashboard; regenerated periodically."""

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="summary")
    summary_text = models.TextField(blank=True)
    action_points = models.JSONField(default=list, blank=True)
    urgent_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Summary for {self.customer}"


class Draft(models.Model):
    """An auto-generated (or edited) reply draft for a customer thread."""

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_DISCARDED = "discarded"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_DISCARDED, "Discarded"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drafts")
    communication = models.ForeignKey(
        CommunicationLog, on_delete=models.CASCADE, related_name="drafts", null=True, blank=True
    )
    subject = models.CharField(max_length=998, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    generated_by = models.CharField(max_length=50, default="assistant")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Draft for {self.customer} ({self.status})"
