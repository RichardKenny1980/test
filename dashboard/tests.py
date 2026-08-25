import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from gtasks.models import TaskItem

User = get_user_model()


class DashboardViewTests(TestCase):
    def test_renders_with_no_data(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No customers yet")

    def test_renders_customer_cards(self):
        Customer.objects.create(name="Acme", company_domain="acmecorp.com")
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme")

    def test_includes_auto_refresh_attribute(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "data-refresh-seconds=\"30\"")

    def test_renders_theme_toggle(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, 'id="theme-toggle"')

    def test_renders_due_today_panel_when_empty(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Top 10 due today")
        self.assertContains(response, "Nothing due today")

    def test_renders_due_today_items(self):
        user = User.objects.create_user(username="rep@example.com")
        customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")
        TaskItem.objects.create(
            user=user,
            customer=customer,
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
