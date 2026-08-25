import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from communications.models import CommunicationLog
from customers.models import Customer
from gcal.models import CalendarEvent
from gtasks.models import TaskItem

from .services import top_actions_today, todays_meetings, urgent_counts

User = get_user_model()


class DashboardServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com", email="rep@example.com")
        self.other = User.objects.create_user(username="other@example.com", email="other@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def _task(self, title, due, user=None, status=TaskItem.STATUS_NEEDS_ACTION, is_urgent=False):
        return TaskItem.objects.create(
            user=user or self.user,
            customer=self.customer,
            google_task_id=f"t-{title}-{(user or self.user).id}",
            task_list_id="l1",
            title=title,
            due=due,
            status=status,
            is_urgent=is_urgent,
        )

    def _comm(self, external_id, subject, occurred_at, user=None, is_urgent=True, source=None):
        return CommunicationLog.objects.create(
            user=user or self.user,
            customer=self.customer,
            source=source or CommunicationLog.SOURCE_EMAIL,
            external_id=external_id,
            subject=subject,
            occurred_at=occurred_at,
            is_urgent=is_urgent,
        )

    def _event(self, title, start, user=None, **kwargs):
        return CalendarEvent.objects.create(
            user=user or self.user,
            customer=kwargs.pop("customer", self.customer),
            google_event_id=f"e-{title}-{(user or self.user).id}",
            calendar_id="primary",
            title=title,
            start=start,
            end=kwargs.pop("end", start + datetime.timedelta(hours=1)),
            **kwargs,
        )


class TopActionsTodayTests(DashboardServiceTestCase):
    def test_empty_when_nothing_due(self):
        self._task("Next week", timezone.now() + datetime.timedelta(days=7))
        self.assertEqual(top_actions_today(self.user), [])

    def test_excludes_other_users_tasks(self):
        self._task("Mine", timezone.now() - datetime.timedelta(days=1))
        self._task("Theirs", timezone.now() - datetime.timedelta(days=1), user=self.other)

        titles = [item["title"] for item in top_actions_today(self.user)]

        self.assertEqual(titles, ["Mine"])

    def test_excludes_other_users_messages(self):
        self._comm("m-mine", "Mine", timezone.now())
        self._comm("m-theirs", "Theirs", timezone.now(), user=self.other)

        titles = [item["title"] for item in top_actions_today(self.user)]

        self.assertEqual(titles, ["Mine"])

    def test_anonymous_user_gets_nothing(self):
        from django.contrib.auth.models import AnonymousUser

        self._task("Mine", timezone.now() - datetime.timedelta(days=1))

        self.assertEqual(top_actions_today(AnonymousUser()), [])

    def test_ranking_overdue_then_due_today_then_messages(self):
        self._comm("m1", "Urgent mail", timezone.now() - datetime.timedelta(hours=1))
        self._task("Due today", timezone.now() + datetime.timedelta(hours=2))
        self._task("Overdue", timezone.now() - datetime.timedelta(days=2))

        titles = [item["title"] for item in top_actions_today(self.user)]

        self.assertEqual(titles, ["Overdue", "Due today", "Urgent mail"])

    def test_older_overdue_ranks_above_newer_overdue(self):
        self._task("Recent", timezone.now() - datetime.timedelta(days=1))
        self._task("Ancient", timezone.now() - datetime.timedelta(days=10))

        titles = [item["title"] for item in top_actions_today(self.user)]

        self.assertEqual(titles, ["Ancient", "Recent"])

    def test_newer_urgent_message_ranks_above_older(self):
        self._comm("m-old", "Older", timezone.now() - datetime.timedelta(days=3))
        self._comm("m-new", "Newer", timezone.now() - datetime.timedelta(hours=1))

        titles = [item["title"] for item in top_actions_today(self.user)]

        self.assertEqual(titles, ["Newer", "Older"])

    def test_includes_chat_messages_not_just_email(self):
        self._comm(
            "c1", "Escalation in space", timezone.now(), source=CommunicationLog.SOURCE_CHAT
        )

        items = top_actions_today(self.user)

        self.assertEqual(items[0]["source_label"], "Chat")

    def test_includes_undated_urgent_task_last(self):
        self._task("Overdue", timezone.now() - datetime.timedelta(days=1))
        self._task("Undated urgent", None, is_urgent=True)

        titles = [item["title"] for item in top_actions_today(self.user)]

        self.assertEqual(titles, ["Overdue", "Undated urgent"])

    def test_ignores_undated_task_that_is_not_urgent(self):
        self._task("Undated calm", None, is_urgent=False)

        self.assertEqual(top_actions_today(self.user), [])

    def test_excludes_completed_tasks(self):
        self._task(
            "Done", timezone.now() - datetime.timedelta(days=1), status=TaskItem.STATUS_COMPLETED
        )
        self.assertEqual(top_actions_today(self.user), [])

    def test_ignores_non_urgent_messages(self):
        self._comm("m1", "Just checking in", timezone.now(), is_urgent=False)
        self.assertEqual(top_actions_today(self.user), [])

    def test_ignores_stale_urgent_messages(self):
        self._comm("m1", "Old urgent", timezone.now() - datetime.timedelta(days=30))
        self.assertEqual(top_actions_today(self.user), [])

    def test_caps_at_limit(self):
        for i in range(15):
            self._task(f"Task {i}", timezone.now() - datetime.timedelta(hours=i + 1))

        self.assertEqual(len(top_actions_today(self.user, limit=10)), 10)

    def test_meetings_do_not_consume_action_slots(self):
        self._event("Standup", timezone.localtime().replace(hour=9, minute=0))

        self.assertEqual(top_actions_today(self.user), [])


class TodaysMeetingsTests(DashboardServiceTestCase):
    def _today_at(self, hour, minute=0):
        return timezone.localtime().replace(hour=hour, minute=minute, second=0, microsecond=0)

    def test_returns_todays_meetings_in_time_order(self):
        self._event("Afternoon sync", self._today_at(15))
        self._event("Morning standup", self._today_at(9))

        titles = [event.title for event in todays_meetings(self.user)]

        self.assertEqual(titles, ["Morning standup", "Afternoon sync"])

    def test_excludes_other_users_meetings(self):
        self._event("Mine", self._today_at(10))
        self._event("Theirs", self._today_at(11), user=self.other)

        titles = [event.title for event in todays_meetings(self.user)]

        self.assertEqual(titles, ["Mine"])

    def test_excludes_meetings_on_other_days(self):
        self._event("Tomorrow", timezone.localtime() + datetime.timedelta(days=1))

        self.assertEqual(todays_meetings(self.user), [])

    def test_anonymous_user_gets_nothing(self):
        from django.contrib.auth.models import AnonymousUser

        self._event("Mine", self._today_at(10))

        self.assertEqual(todays_meetings(AnonymousUser()), [])

    def test_external_attendees_excludes_the_user(self):
        event = self._event(
            "Renewal call",
            self._today_at(10),
            attendees=[
                {"email": "rep@example.com", "name": "Rep"},
                {"email": "jane@acmecorp.com", "name": "Jane Doe"},
            ],
        )

        others = event.external_attendees

        self.assertEqual([a["email"] for a in others], ["jane@acmecorp.com"])

    def test_meta_line_joins_customer_attendees_and_location(self):
        event = self._event(
            "Renewal call",
            self._today_at(10),
            location="Room 4B",
            attendees=[
                {"email": "rep@example.com", "name": "Rep"},
                {"email": "jane@acmecorp.com", "name": "Jane Doe"},
            ],
        )

        self.assertEqual(event.meta_line, "Acme · Jane Doe · Room 4B")

    def test_meta_line_has_no_leading_separator_when_parts_missing(self):
        event = self._event(
            "Internal review",
            self._today_at(14),
            customer=None,
            location="Room 4B",
            attendees=[{"email": "rep@example.com", "name": "Rep"}],
        )

        self.assertEqual(event.meta_line, "Room 4B")

    def test_meta_line_truncates_long_attendee_lists(self):
        event = self._event(
            "Big meeting",
            self._today_at(11),
            customer=None,
            attendees=[{"email": f"p{i}@acmecorp.com", "name": f"Person {i}"} for i in range(6)],
        )

        self.assertIn("+3 more", event.meta_line)

    def test_meta_line_empty_when_nothing_to_show(self):
        event = self._event("Solo focus block", self._today_at(16), customer=None)

        self.assertEqual(event.meta_line, "")

    def test_in_progress_flag(self):
        now = timezone.now()
        live = self._event("Live now", now - datetime.timedelta(minutes=10))
        later = self._event("Later", now + datetime.timedelta(hours=3))

        self.assertTrue(live.is_in_progress)
        self.assertFalse(later.is_in_progress)


class UrgentCountsTests(DashboardServiceTestCase):
    def test_counts_only_this_users_items(self):
        self._comm("m1", "Mine", timezone.now())
        self._comm("m2", "Theirs", timezone.now(), user=self.other)
        self._task("Mine urgent", None, is_urgent=True)

        self.assertEqual(urgent_counts(self.user), 2)

    def test_excludes_completed_urgent_tasks(self):
        self._task("Done", None, is_urgent=True, status=TaskItem.STATUS_COMPLETED)

        self.assertEqual(urgent_counts(self.user), 0)

    def test_anonymous_user_counts_zero(self):
        from django.contrib.auth.models import AnonymousUser

        self._comm("m1", "Mine", timezone.now())

        self.assertEqual(urgent_counts(AnonymousUser()), 0)
