import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communications.models import CommunicationLog
from customers.models import Customer
from gcal.models import CalendarEvent
from gtasks.models import TaskItem

User = get_user_model()


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rep@example.com", email="rep@example.com", password="pw"
        )
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def _login(self):
        self.client.force_login(self.user)

    def test_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in with Google")

    def test_renders_with_no_data(self):
        self._login()
        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No customers yet")

    def test_includes_auto_refresh_attribute(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, 'data-refresh-seconds="30"')

    def test_renders_theme_toggle(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, 'id="theme-toggle"')

    def test_renders_due_today_items_for_logged_in_user(self):
        self._login()
        TaskItem.objects.create(
            user=self.user,
            customer=self.customer,
            google_task_id="t1",
            task_list_id="l1",
            title="Send the renewal quote",
            due=timezone.now() - datetime.timedelta(days=1),
            status=TaskItem.STATUS_NEEDS_ACTION,
        )

        response = self.client.get(reverse("dashboard:index"))

        self.assertContains(response, "Send the renewal quote")
        self.assertContains(response, "Overdue")
        self.assertEqual(len(response.context["due_today"]), 1)

    def test_does_not_leak_another_users_items(self):
        other = User.objects.create_user(username="other@example.com", email="other@example.com")
        TaskItem.objects.create(
            user=other,
            customer=self.customer,
            google_task_id="t-other",
            task_list_id="l1",
            title="Someone elses task",
            due=timezone.now() - datetime.timedelta(days=1),
            status=TaskItem.STATUS_NEEDS_ACTION,
        )
        self._login()

        response = self.client.get(reverse("dashboard:index"))

        self.assertNotContains(response, "Someone elses task")
        self.assertEqual(len(response.context["due_today"]), 0)

    def test_renders_todays_meetings(self):
        self._login()
        CalendarEvent.objects.create(
            user=self.user,
            customer=self.customer,
            google_event_id="e1",
            calendar_id="primary",
            title="Acme renewal call",
            start=timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0),
            end=timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0),
            attendees=[{"email": "jane@acmecorp.com", "name": "Jane Doe"}],
        )

        response = self.client.get(reverse("dashboard:index"))

        self.assertContains(response, "Meetings today")
        self.assertContains(response, "Acme renewal call")
        self.assertContains(response, "Jane Doe")

    def test_hides_meetings_section_when_none(self):
        self._login()
        response = self.client.get(reverse("dashboard:index"))

        self.assertNotContains(response, "Meetings today")

    def test_only_shows_customers_the_user_has_activity_with(self):
        mine = Customer.objects.create(name="MyCustomer", company_domain="mine.com")
        Customer.objects.create(name="TheirCustomer", company_domain="theirs.com")
        CommunicationLog.objects.create(
            user=self.user,
            customer=mine,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m1",
            subject="Hello",
            occurred_at=timezone.now(),
        )
        self._login()

        response = self.client.get(reverse("dashboard:index"))

        self.assertContains(response, "MyCustomer")
        self.assertNotContains(response, "TheirCustomer")

    def test_urgent_badge_counts_only_this_user(self):
        other = User.objects.create_user(username="other2@example.com", email="other2@example.com")
        CommunicationLog.objects.create(
            user=other,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m-other",
            subject="Their urgent thing",
            is_urgent=True,
            occurred_at=timezone.now(),
        )
        self._login()

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.context["total_urgent"], 0)
