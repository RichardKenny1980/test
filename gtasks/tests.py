from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from communications.models import CustomerSummary
from customers.models import Customer

from . import tasks
from .models import TaskItem

User = get_user_model()


class SyncTasksForUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    @patch("gtasks.tasks.fetch_all_tasks")
    @patch("gtasks.tasks.get_credentials")
    def test_no_credentials_skips_sync(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = None

        count = tasks.sync_tasks_for_user(self.user.id)

        self.assertEqual(count, 0)
        mock_fetch.assert_not_called()
        self.assertEqual(TaskItem.objects.count(), 0)

    @patch("gtasks.tasks.fetch_all_tasks")
    @patch("gtasks.tasks.get_credentials")
    def test_creates_task_and_flags_overdue(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = MagicMock()
        mock_fetch.return_value = [
            {
                "google_task_id": "gtask-1",
                "task_list_id": "list-1",
                "title": "Follow up",
                "notes": "",
                "status": TaskItem.STATUS_NEEDS_ACTION,
                "due": timezone.now() - timezone.timedelta(days=2),
                "google_updated_at": timezone.now(),
            }
        ]

        count = tasks.sync_tasks_for_user(self.user.id)

        self.assertEqual(count, 1)
        item = TaskItem.objects.get(google_task_id="gtask-1")
        self.assertTrue(item.is_urgent)

    @patch("gtasks.tasks.fetch_all_tasks")
    @patch("gtasks.tasks.get_credentials")
    def test_matches_customer_from_notes_and_refreshes_summary(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = MagicMock()
        mock_fetch.return_value = [
            {
                "google_task_id": "gtask-2",
                "task_list_id": "list-1",
                "title": "Send proposal",
                "notes": "Contact jane@acmecorp.com for details",
                "status": TaskItem.STATUS_NEEDS_ACTION,
                "due": None,
                "google_updated_at": None,
            }
        ]

        tasks.sync_tasks_for_user(self.user.id)

        item = TaskItem.objects.get(google_task_id="gtask-2")
        self.assertIsNotNone(item.customer)
        self.assertEqual(item.customer.company_domain, "acmecorp.com")
        self.assertTrue(CustomerSummary.objects.filter(customer=item.customer).exists())

    @patch("gtasks.tasks.fetch_all_tasks")
    @patch("gtasks.tasks.get_credentials")
    def test_upsert_updates_existing_task_instead_of_duplicating(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = MagicMock()
        mock_fetch.return_value = [
            {
                "google_task_id": "gtask-3",
                "task_list_id": "list-1",
                "title": "Draft v1",
                "notes": "",
                "status": TaskItem.STATUS_NEEDS_ACTION,
                "due": None,
                "google_updated_at": None,
            }
        ]
        tasks.sync_tasks_for_user(self.user.id)

        mock_fetch.return_value = [
            {
                "google_task_id": "gtask-3",
                "task_list_id": "list-1",
                "title": "Draft v2",
                "notes": "",
                "status": TaskItem.STATUS_COMPLETED,
                "due": None,
                "google_updated_at": None,
            }
        ]
        tasks.sync_tasks_for_user(self.user.id)

        self.assertEqual(TaskItem.objects.filter(google_task_id="gtask-3").count(), 1)
        item = TaskItem.objects.get(google_task_id="gtask-3")
        self.assertEqual(item.title, "Draft v2")
        self.assertEqual(item.status, TaskItem.STATUS_COMPLETED)
