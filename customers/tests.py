from django.test import TestCase

from .models import Customer, CustomerEmailAlias
from .utils import (
    extract_domain,
    find_customer_by_text,
    get_or_create_customer_for_email,
    group_emails_by_customer,
    is_personal_domain,
    normalize_email,
)


class NormalizationTests(TestCase):
    def test_normalize_email_lowercases_and_strips(self):
        self.assertEqual(normalize_email("  Jane@Example.COM  "), "jane@example.com")

    def test_normalize_email_handles_none(self):
        self.assertEqual(normalize_email(None), "")

    def test_extract_domain(self):
        self.assertEqual(extract_domain("jane@example.com"), "example.com")

    def test_extract_domain_no_at_sign(self):
        self.assertEqual(extract_domain("not-an-email"), "")

    def test_is_personal_domain(self):
        self.assertTrue(is_personal_domain("gmail.com"))
        self.assertFalse(is_personal_domain("acmecorp.com"))


class CustomerGroupingTests(TestCase):
    def test_creates_new_customer_for_unseen_company_email(self):
        customer = get_or_create_customer_for_email("jane@acmecorp.com")

        self.assertIsNotNone(customer)
        self.assertEqual(customer.company_domain, "acmecorp.com")
        self.assertEqual(customer.primary_email, "jane@acmecorp.com")
        self.assertTrue(CustomerEmailAlias.objects.filter(email="jane@acmecorp.com").exists())

    def test_groups_two_contacts_at_same_company_domain(self):
        jane = get_or_create_customer_for_email("jane@acmecorp.com")
        bob = get_or_create_customer_for_email("bob@acmecorp.com")

        self.assertEqual(jane.pk, bob.pk)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CustomerEmailAlias.objects.filter(customer=jane).count(), 2)

    def test_same_email_seen_twice_reuses_customer_and_does_not_duplicate_alias(self):
        first = get_or_create_customer_for_email("jane@acmecorp.com")
        second = get_or_create_customer_for_email("jane@acmecorp.com")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(CustomerEmailAlias.objects.filter(email="jane@acmecorp.com").count(), 1)

    def test_case_and_whitespace_insensitive_matching(self):
        first = get_or_create_customer_for_email("Jane@AcmeCorp.com")
        second = get_or_create_customer_for_email("  jane@acmecorp.com  ")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Customer.objects.count(), 1)

    def test_personal_domains_do_not_group_by_domain(self):
        jane = get_or_create_customer_for_email("jane.doe@gmail.com")
        bob = get_or_create_customer_for_email("bob.smith@gmail.com")

        self.assertNotEqual(jane.pk, bob.pk)
        self.assertEqual(jane.company_domain, "")
        self.assertEqual(Customer.objects.count(), 2)

    def test_empty_email_returns_none(self):
        self.assertIsNone(get_or_create_customer_for_email(""))
        self.assertIsNone(get_or_create_customer_for_email(None))

    def test_name_backfills_blank_customer_name(self):
        customer = get_or_create_customer_for_email("jane@acmecorp.com")
        self.assertEqual(customer.name, "")

        updated = get_or_create_customer_for_email("bob@acmecorp.com", name="Acme Corp")
        self.assertEqual(updated.pk, customer.pk)
        self.assertEqual(updated.name, "Acme Corp")

    def test_name_does_not_overwrite_existing_name(self):
        get_or_create_customer_for_email("jane@acmecorp.com", name="Acme Corp")
        updated = get_or_create_customer_for_email("bob@acmecorp.com", name="Different Name")

        self.assertEqual(updated.name, "Acme Corp")

    def test_group_emails_by_customer_maps_each_address(self):
        mapping = group_emails_by_customer(["jane@acmecorp.com", "bob@acmecorp.com", "x@gmail.com"])

        self.assertEqual(mapping["jane@acmecorp.com"].pk, mapping["bob@acmecorp.com"].pk)
        self.assertNotEqual(mapping["x@gmail.com"].pk, mapping["jane@acmecorp.com"].pk)


class FindCustomerByTextTests(TestCase):
    def test_finds_email_embedded_in_text(self):
        customer = find_customer_by_text("Follow up with jane@acmecorp.com about the contract")
        self.assertIsNotNone(customer)
        self.assertEqual(customer.company_domain, "acmecorp.com")

    def test_returns_none_when_no_email_present(self):
        self.assertIsNone(find_customer_by_text("Just a plain task with no contact info"))

    def test_returns_none_for_empty_text(self):
        self.assertIsNone(find_customer_by_text(""))
        self.assertIsNone(find_customer_by_text(None))
