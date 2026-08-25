import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from customers.models import Customer

from . import tasks
from .models import CalendarEvent
from .services import normalize_event

User = get_user_model()


class NormalizeEventTests(TestCase):
    def test_parses_timed_event(self):
        result = normalize_event(
            {
                "id": "evt-1",
                "summary": "Renewal call",
                "location": "Zoom",
                "start": {"dateTime": "2026-08-25T10:00:00Z"},
                "end": {"dateTime": "2026-08-25T11:00:00Z"},
                "hangoutLink": "https://meet.google.com/abc",
                "organizer": {"email": "rep@example.com"},
            },
            "primary",
        )

        self.assertEqual(result["title"], "Renewal call")
        self.assertFalse(result["is_all_day"])
        self.assertEqual(result["conference_url"], "https://meet.google.com/abc")
        self.assertEqual(result["start"].hour, 10)

    def test_parses_all_day_event(self):
        result = normalize_event(
            {"id": "evt-2", "summary": "Company offsite", "start": {"date": "2026-08-25"}},
            "primary",
        )

        self.assertTrue(result["is_all_day"])
        self.assertIsNotNone(result["start"])

    def test_extracts_attendees_and_skips_rooms(self):
        result = normalize_event(
            {
                "id": "evt-3",
                "summary": "Sync",
                "start": {"dateTime": "2026-08-25T10:00:00Z"},
                "attendees": [
                    {"email": "jane@acmecorp.com", "displayName": "Jane", "responseStatus": "accepted"},
                    {"email": "room-4@resource.calendar.google.com", "resource": True},
                ],
            },
            "primary",
        )

        self.assertEqual([a["email"] for a in result["attendees"]], ["jane@acmecorp.com"])

    def test_falls_back_to_conference_entry_point(self):
        result = normalize_event(
            {
                "id": "evt-4",
                "summary": "Sync",
                "start": {"dateTime": "2026-08-25T10:00:00Z"},
                "conferenceData": {
                    "entryPoints": [
                        {"entryPointType": "phone", "uri": "tel:+123"},
                        {"entryPointType": "video", "uri": "https://meet.example/xyz"},
                    ]
                },
            },
            "primary",
        )

        self.assertEqual(result["conference_url"], "https://meet.example/xyz")


class SyncCalendarForUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com", email="rep@example.com")

    def _event_payload(self, **overrides):
        payload = {
            "google_event_id": "evt-1",
            "calendar_id": "primary",
            "title": "Renewal call",
            "description": "",
            "location": "",
            "conference_url": "",
            "start": timezone.now() + datetime.timedelta(hours=2),
            "end": timezone.now() + datetime.timedelta(hours=3),
            "is_all_day": False,
            "attendees": [],
            "organizer_email": "rep@example.com",
        }
        payload.update(overrides)
        return payload

    @patch("gcal.tasks.fetch_events")
    @patch("gcal.tasks.get_gmail_chat_credentials")
    def test_no_credentials_skips_sync(self, mock_creds, mock_fetch):
        mock_creds.return_value = None

        self.assertEqual(tasks.sync_calendar_for_user(self.user.id), 0)
        mock_fetch.assert_not_called()

    @patch("gcal.tasks.fetch_events")
    @patch("gcal.tasks.get_gmail_chat_credentials")
    def test_creates_event(self, mock_creds, mock_fetch):
        mock_creds.return_value = MagicMock()
        mock_fetch.return_value = [self._event_payload()]

        count = tasks.sync_calendar_for_user(self.user.id)

        self.assertEqual(count, 1)
        self.assertTrue(CalendarEvent.objects.filter(google_event_id="evt-1").exists())

    @patch("gcal.tasks.fetch_events")
    @patch("gcal.tasks.get_gmail_chat_credentials")
    def test_links_customer_from_external_attendee(self, mock_creds, mock_fetch):
        mock_creds.return_value = MagicMock()
        mock_fetch.return_value = [
            self._event_payload(
                attendees=[
                    {"email": "rep@example.com", "name": "Rep"},
                    {"email": "jane@acmecorp.com", "name": "Jane Doe"},
                ]
            )
        ]

        tasks.sync_calendar_for_user(self.user.id)

        event = CalendarEvent.objects.get(google_event_id="evt-1")
        self.assertIsNotNone(event.customer)
        self.assertEqual(event.customer.company_domain, "acmecorp.com")

    @patch("gcal.tasks.fetch_events")
    @patch("gcal.tasks.get_gmail_chat_credentials")
    def test_internal_only_meeting_has_no_customer(self, mock_creds, mock_fetch):
        mock_creds.return_value = MagicMock()
        mock_fetch.return_value = [
            self._event_payload(
                attendees=[
                    {"email": "rep@example.com", "name": "Rep"},
                    {"email": "colleague@example.com", "name": "Colleague"},
                ]
            )
        ]

        tasks.sync_calendar_for_user(self.user.id)

        self.assertIsNone(CalendarEvent.objects.get(google_event_id="evt-1").customer)
        self.assertEqual(Customer.objects.count(), 0)

    @patch("gcal.tasks.fetch_events")
    @patch("gcal.tasks.get_gmail_chat_credentials")
    def test_resync_updates_instead_of_duplicating(self, mock_creds, mock_fetch):
        mock_creds.return_value = MagicMock()
        mock_fetch.return_value = [self._event_payload(title="Original")]
        tasks.sync_calendar_for_user(self.user.id)

        mock_fetch.return_value = [self._event_payload(title="Renamed")]
        tasks.sync_calendar_for_user(self.user.id)

        self.assertEqual(CalendarEvent.objects.filter(google_event_id="evt-1").count(), 1)
        self.assertEqual(CalendarEvent.objects.get(google_event_id="evt-1").title, "Renamed")
