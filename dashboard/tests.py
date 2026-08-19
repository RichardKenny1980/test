from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


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
