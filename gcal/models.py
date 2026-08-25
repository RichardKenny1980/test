from django.conf import settings
from django.db import models
from django.utils import timezone

from customers.models import Customer


class CalendarEvent(models.Model):
    """A Google Calendar event, normalized and linked to a customer.

    Only events the user is actually attending are worth surfacing, so
    declined events are filtered out at sync time.
    """

    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_events"
    )
    google_event_id = models.CharField(max_length=255)
    calendar_id = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=1024, blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=1024, blank=True)
    conference_url = models.URLField(max_length=1024, blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    # [{"email": ..., "name": ..., "organizer": bool, "response": "accepted"}]
    attendees = models.JSONField(default=list, blank=True)
    organizer_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "google_event_id"], name="unique_event_per_user"
            ),
        ]
        indexes = [models.Index(fields=["user", "start"])]

    def __str__(self):
        return self.title or self.google_event_id

    @property
    def external_attendees(self):
        """Attendees who aren't the event owner - who you're actually meeting."""
        owner = (self.user.email or "").lower()
        return [a for a in self.attendees if (a.get("email") or "").lower() != owner]

    @property
    def meta_line(self, max_names=3):
        """Customer, who's attending, and where - joined without stray separators.

        Built here rather than in the template because conditional separators
        between optional parts are exactly the kind of thing template logic
        gets wrong.
        """
        parts = []
        if self.customer:
            parts.append(str(self.customer))

        others = self.external_attendees
        if others:
            names = [a.get("name") or a.get("email") or "" for a in others[:max_names]]
            names = [n for n in names if n]
            if names:
                label = ", ".join(names)
                remaining = len(others) - len(names)
                if remaining > 0:
                    label += f" +{remaining} more"
                parts.append(label)

        if self.location:
            parts.append(self.location)

        return " · ".join(parts)

    @property
    def is_in_progress(self):
        now = timezone.now()
        return self.start <= now and (self.end or self.start) >= now
