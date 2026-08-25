import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from communications.models import CommunicationLog
from customers.models import Customer
from gtasks.models import TaskItem

from .services import top_items_due_today

User = get_user_model()


class TopItemsDueTodayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def _task(self, title, due, status=TaskItem.STATUS_NEEDS_ACTION, **kwargs):
        return TaskItem.objects.create(
            user=self.user,
            customer=self.customer,
            google_task_id=f"t-{title}",
            task_list_id="list-1",
            title=title,
            due=due,
            status=status,
            **kwargs,
        )

    def _comm(self, external_id, subject, occurred_at, is_urgent=False):
        return CommunicationLog.objects.create(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id=external_id,
            subject=subject,
            occurred_at=occurred_at,
            is_urgent=is_urgent,
        )

    def test_empty_when_nothing_due(self):
        self._task("Next week", timezone.now() + datetime.timedelta(days=7))
        self.assertEqual(top_items_due_today(), [])

    def test_includes_overdue_and_due_today_tasks(self):
        self._task("Overdue", timezone.now() - datetime.timedelta(days=2))
        self._task("Due today", timezone.now() + datetime.timedelta(minutes=30))

        items = top_items_due_today()

        titles = [item["title"] for item in items]
        self.assertIn("Overdue", titles)
        self.assertIn("Due today", titles)

    def test_overdue_flagged_and_ordered_first(self):
        self._task("Due today", timezone.now() + datetime.timedelta(minutes=30))
        self._task("Overdue", timezone.now() - datetime.timedelta(days=3))

        items = top_items_due_today()

        self.assertEqual(items[0]["title"], "Overdue")
        self.assertTrue(items[0]["is_overdue"])
        self.assertFalse(items[1]["is_overdue"])

    def test_excludes_completed_tasks(self):
        self._task("Done", timezone.now() - datetime.timedelta(days=1), status=TaskItem.STATUS_COMPLETED)
        self.assertEqual(top_items_due_today(), [])

    def test_excludes_future_tasks(self):
        self._task("Tomorrow", timezone.now() + datetime.timedelta(days=2))
        self.assertEqual(top_items_due_today(), [])

    def test_fills_remaining_slots_with_recent_urgent_communications(self):
        self._task("Overdue", timezone.now() - datetime.timedelta(days=1))
        self._comm("m1", "URGENT: contract", timezone.now() - datetime.timedelta(hours=2), is_urgent=True)

        items = top_items_due_today()

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["kind"], "task")
        self.assertEqual(items[1]["kind"], CommunicationLog.SOURCE_EMAIL)
        self.assertTrue(items[1]["is_urgent"])

    def test_ignores_non_urgent_communications(self):
        self._comm("m1", "Just checking in", timezone.now(), is_urgent=False)
        self.assertEqual(top_items_due_today(), [])

    def test_ignores_stale_urgent_communications(self):
        self._comm("m1", "Old urgent", timezone.now() - datetime.timedelta(days=30), is_urgent=True)
        self.assertEqual(top_items_due_today(), [])

    def test_caps_at_limit(self):
        for i in range(15):
            self._task(f"Task {i}", timezone.now() - datetime.timedelta(hours=i + 1))

        self.assertEqual(len(top_items_due_today(limit=10)), 10)

    def test_tasks_crowd_out_communications_when_full(self):
        for i in range(10):
            self._task(f"Task {i}", timezone.now() - datetime.timedelta(hours=i + 1))
        self._comm("m1", "URGENT", timezone.now(), is_urgent=True)

        items = top_items_due_today(limit=10)

        self.assertEqual(len(items), 10)
        self.assertTrue(all(item["kind"] == "task" for item in items))

    def test_item_carries_customer_for_display(self):
        self._task("Overdue", timezone.now() - datetime.timedelta(days=1))

        items = top_items_due_today()

        self.assertEqual(items[0]["customer"], self.customer)
