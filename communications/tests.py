import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from customers.models import Customer
from customers.utils import get_or_create_customer_for_email
from gtasks.models import TaskItem

from . import summarizer, tasks
from .models import CommunicationLog, CustomerSummary, Draft

User = get_user_model()


class DetectUrgencyTests(TestCase):
    def test_flags_known_keyword(self):
        is_urgent, reason = summarizer.detect_urgency("Please respond ASAP, this is critical")
        self.assertTrue(is_urgent)
        self.assertIn("asap", reason.lower())

    def test_case_insensitive(self):
        is_urgent, _ = summarizer.detect_urgency("This is URGENT")
        self.assertTrue(is_urgent)

    def test_no_keyword_not_urgent(self):
        is_urgent, reason = summarizer.detect_urgency("Just checking in, no rush")
        self.assertFalse(is_urgent)
        self.assertEqual(reason, "")

    def test_empty_text(self):
        is_urgent, reason = summarizer.detect_urgency("")
        self.assertFalse(is_urgent)
        self.assertEqual(reason, "")


class FlagCommunicationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def _make_comm(self, **overrides):
        defaults = dict(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="msg-1",
            subject="Hello",
            snippet="just a note",
            body_text="",
            occurred_at=timezone.now(),
        )
        defaults.update(overrides)
        return CommunicationLog.objects.create(**defaults)

    def test_flags_urgent_message(self):
        comm = self._make_comm(subject="URGENT: contract deadline")
        summarizer.flag_communication(comm)

        comm.refresh_from_db()
        self.assertTrue(comm.is_urgent)
        self.assertNotEqual(comm.urgency_reason, "")

    def test_does_not_flag_normal_message(self):
        comm = self._make_comm(subject="Following up", snippet="Thanks for the call")
        summarizer.flag_communication(comm)

        comm.refresh_from_db()
        self.assertFalse(comm.is_urgent)


class FlagTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    def _make_task(self, **overrides):
        defaults = dict(
            user=self.user,
            google_task_id="task-1",
            task_list_id="list-1",
            title="Send proposal",
            status=TaskItem.STATUS_NEEDS_ACTION,
        )
        defaults.update(overrides)
        return TaskItem.objects.create(**defaults)

    def test_flags_overdue_task(self):
        task = self._make_task(due=timezone.now() - datetime.timedelta(days=1))
        summarizer.flag_task(task)

        task.refresh_from_db()
        self.assertTrue(task.is_urgent)

    def test_completed_overdue_task_not_flagged(self):
        task = self._make_task(
            due=timezone.now() - datetime.timedelta(days=1), status=TaskItem.STATUS_COMPLETED
        )
        summarizer.flag_task(task)

        task.refresh_from_db()
        self.assertFalse(task.is_urgent)

    def test_flags_task_with_urgent_keyword(self):
        task = self._make_task(title="Critical: fix billing issue", due=None)
        summarizer.flag_task(task)

        task.refresh_from_db()
        self.assertTrue(task.is_urgent)

    def test_future_due_no_keyword_not_flagged(self):
        task = self._make_task(due=timezone.now() + datetime.timedelta(days=3))
        summarizer.flag_task(task)

        task.refresh_from_db()
        self.assertFalse(task.is_urgent)


class BuildCustomerSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def test_summary_includes_communications_and_urgent_action_points(self):
        CommunicationLog.objects.create(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m1",
            subject="URGENT: renewal",
            sender_email="jane@acmecorp.com",
            is_urgent=True,
            urgency_reason="Contains urgency keyword: 'urgent'",
            occurred_at=timezone.now(),
        )
        TaskItem.objects.create(
            user=self.user,
            customer=self.customer,
            google_task_id="t1",
            task_list_id="l1",
            title="Prepare renewal doc",
            status=TaskItem.STATUS_NEEDS_ACTION,
        )

        summary = summarizer.build_customer_summary(self.customer)

        self.assertIn("recent message", summary.summary_text)
        self.assertIn("open task", summary.summary_text)
        self.assertEqual(summary.urgent_count, 1)
        self.assertTrue(any("URGENT: renewal" in point for point in summary.action_points))

    def test_summary_handles_no_activity(self):
        summary = summarizer.build_customer_summary(self.customer)
        self.assertIn("No recent communications", summary.summary_text)
        self.assertEqual(summary.urgent_count, 0)

    def test_summary_is_cached_and_updated_in_place(self):
        summarizer.build_customer_summary(self.customer)
        self.assertEqual(CustomerSummary.objects.filter(customer=self.customer).count(), 1)

        CommunicationLog.objects.create(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m2",
            subject="Hi",
            occurred_at=timezone.now(),
        )
        summarizer.build_customer_summary(self.customer)
        self.assertEqual(CustomerSummary.objects.filter(customer=self.customer).count(), 1)


class GenerateDraftReplyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def test_generates_draft_referencing_sender_and_subject(self):
        comm = CommunicationLog.objects.create(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m1",
            subject="Contract question",
            snippet="Can we adjust the terms?",
            sender_name="Jane Doe",
            sender_email="jane@acmecorp.com",
            occurred_at=timezone.now(),
        )

        draft = summarizer.generate_draft_reply(comm)

        self.assertEqual(draft.status, Draft.STATUS_DRAFT)
        self.assertIn("Jane Doe", draft.body)
        self.assertIn("Contract question", draft.body)
        self.assertEqual(draft.subject, "Re: Contract question")

    def test_falls_back_to_email_local_part_without_sender_name(self):
        comm = CommunicationLog.objects.create(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m2",
            sender_email="bob@acmecorp.com",
            occurred_at=timezone.now(),
        )

        draft = summarizer.generate_draft_reply(comm)
        self.assertIn("Hi bob,", draft.body)


class SyncGmailForUserTests(TestCase):
    """Verify the periodic Gmail sync task wires the mocked Google API into
    CommunicationLog rows and customer grouping, without any real network call."""

    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    @patch("communications.tasks.fetch_recent_messages")
    @patch("communications.tasks.get_credentials")
    def test_creates_communication_and_groups_customer(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = MagicMock()
        mock_fetch.return_value = [
            {
                "external_id": "msg-1",
                "thread_id": "thread-1",
                "sender_email": "jane@acmecorp.com",
                "sender_name": "Jane Doe",
                "subject": "URGENT: please review",
                "snippet": "Need this ASAP",
                "body_text": "",
                "occurred_at": timezone.now(),
                "raw_payload": {},
            }
        ]

        count = tasks.sync_gmail_for_user(self.user.id)

        self.assertEqual(count, 1)
        comm = CommunicationLog.objects.get(external_id="msg-1")
        self.assertEqual(comm.customer.company_domain, "acmecorp.com")
        self.assertTrue(comm.is_urgent)
        self.assertTrue(Draft.objects.filter(communication=comm).exists())
        self.assertTrue(CustomerSummary.objects.filter(customer=comm.customer).exists())

    @patch("communications.tasks.fetch_recent_messages")
    @patch("communications.tasks.get_credentials")
    def test_no_credentials_skips_sync(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = None

        count = tasks.sync_gmail_for_user(self.user.id)

        self.assertEqual(count, 0)
        mock_fetch.assert_not_called()
        self.assertEqual(CommunicationLog.objects.count(), 0)

    @patch("communications.tasks.fetch_recent_messages")
    @patch("communications.tasks.get_credentials")
    def test_second_contact_at_same_domain_reuses_customer(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = MagicMock()
        existing_customer = get_or_create_customer_for_email("jane@acmecorp.com")
        mock_fetch.return_value = [
            {
                "external_id": "msg-2",
                "thread_id": "thread-2",
                "sender_email": "bob@acmecorp.com",
                "sender_name": "Bob Smith",
                "subject": "Hi",
                "snippet": "",
                "body_text": "",
                "occurred_at": timezone.now(),
                "raw_payload": {},
            }
        ]

        tasks.sync_gmail_for_user(self.user.id)

        comm = CommunicationLog.objects.get(external_id="msg-2")
        self.assertEqual(comm.customer_id, existing_customer.id)


class SyncChatForUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    @patch("communications.tasks.fetch_recent_space_messages")
    @patch("communications.tasks.get_credentials")
    def test_creates_chat_communication(self, mock_get_credentials, mock_fetch):
        mock_get_credentials.return_value = MagicMock()
        mock_fetch.return_value = [
            {
                "external_id": "spaces/1/messages/1",
                "thread_id": "spaces/1/threads/1",
                "sender_email": "jane@acmecorp.com",
                "sender_name": "Jane Doe",
                "subject": "Project Room",
                "snippet": "Let's sync tomorrow",
                "body_text": "Let's sync tomorrow",
                "occurred_at": timezone.now(),
                "raw_payload": {},
            }
        ]

        count = tasks.sync_chat_for_user(self.user.id)

        self.assertEqual(count, 1)
        comm = CommunicationLog.objects.get(external_id="spaces/1/messages/1")
        self.assertEqual(comm.source, CommunicationLog.SOURCE_CHAT)
        self.assertEqual(comm.customer.company_domain, "acmecorp.com")


@override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
class FlagCommunicationLLMDispatchTests(TestCase):
    """Verify flag_communication/flag_task prefer the LLM when enabled, and
    fall back to the offline heuristic when the LLM call fails (returns None)."""

    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    def _make_comm(self, **overrides):
        defaults = dict(
            user=self.user,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="msg-1",
            subject="Hello",
            snippet="just a note",
            occurred_at=timezone.now(),
        )
        defaults.update(overrides)
        return CommunicationLog.objects.create(**defaults)

    @patch("communications.summarizer.llm.classify_urgency")
    def test_flag_communication_uses_llm_result(self, mock_classify):
        mock_classify.return_value = (True, "Customer threatened to churn")
        comm = self._make_comm(subject="Totally normal subject")

        summarizer.flag_communication(comm)

        comm.refresh_from_db()
        self.assertTrue(comm.is_urgent)
        self.assertEqual(comm.urgency_reason, "Customer threatened to churn")
        mock_classify.assert_called_once()

    @patch("communications.summarizer.llm.classify_urgency")
    def test_falls_back_to_heuristic_when_llm_fails(self, mock_classify):
        mock_classify.return_value = None
        comm = self._make_comm(subject="URGENT: please review")

        summarizer.flag_communication(comm)

        comm.refresh_from_db()
        self.assertTrue(comm.is_urgent)
        self.assertIn("urgent", comm.urgency_reason.lower())

    @patch("communications.summarizer.llm.classify_urgency")
    def test_flag_task_uses_llm_result(self, mock_classify):
        mock_classify.return_value = (True, "Blocking the customer's launch")
        task = TaskItem.objects.create(
            user=self.user,
            google_task_id="task-1",
            task_list_id="list-1",
            title="Ordinary task title",
            status=TaskItem.STATUS_NEEDS_ACTION,
        )

        summarizer.flag_task(task)

        task.refresh_from_db()
        self.assertTrue(task.is_urgent)
        mock_classify.assert_called_once()


@override_settings(USE_LLM=False, ANTHROPIC_API_KEY="")
class FlagCommunicationHeuristicWhenDisabledTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    @patch("communications.summarizer.llm.classify_urgency")
    def test_llm_never_called_when_disabled(self, mock_classify):
        comm = CommunicationLog.objects.create(
            user=self.user,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="msg-1",
            subject="URGENT: please review",
            occurred_at=timezone.now(),
        )

        summarizer.flag_communication(comm)

        mock_classify.assert_not_called()
        comm.refresh_from_db()
        self.assertTrue(comm.is_urgent)


@override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
class BuildCustomerSummaryLLMDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    @patch("communications.summarizer.llm.summarize_customer")
    def test_uses_llm_summary_when_available(self, mock_summarize):
        mock_summarize.return_value = summarizer.llm.CustomerSummaryResult(
            summary="Acme is happy and renewing next month.",
            action_points=["Send renewal contract"],
        )

        summary = summarizer.build_customer_summary(self.customer)

        self.assertEqual(summary.summary_text, "Acme is happy and renewing next month.")
        self.assertEqual(summary.action_points, ["Send renewal contract"])

    @patch("communications.summarizer.llm.summarize_customer")
    def test_falls_back_to_heuristic_when_llm_fails(self, mock_summarize):
        mock_summarize.return_value = None

        summary = summarizer.build_customer_summary(self.customer)

        self.assertIn("No recent communications", summary.summary_text)


@override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
class GenerateDraftReplyLLMDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")
        self.customer = Customer.objects.create(name="Acme", company_domain="acmecorp.com")

    def _make_comm(self):
        return CommunicationLog.objects.create(
            user=self.user,
            customer=self.customer,
            source=CommunicationLog.SOURCE_EMAIL,
            external_id="m1",
            subject="Contract question",
            snippet="Can we adjust the terms?",
            sender_name="Jane Doe",
            sender_email="jane@acmecorp.com",
            occurred_at=timezone.now(),
        )

    @patch("communications.summarizer.llm.draft_reply")
    def test_uses_llm_draft_when_available(self, mock_draft):
        mock_draft.return_value = summarizer.llm.DraftReplyResult(
            subject="Re: Contract question", body="Hi Jane, happy to adjust the terms..."
        )

        draft = summarizer.generate_draft_reply(self._make_comm())

        self.assertEqual(draft.generated_by, "claude")
        self.assertEqual(draft.subject, "Re: Contract question")
        self.assertIn("happy to adjust", draft.body)

    @patch("communications.summarizer.llm.draft_reply")
    def test_falls_back_to_heuristic_when_llm_fails(self, mock_draft):
        mock_draft.return_value = None

        draft = summarizer.generate_draft_reply(self._make_comm())

        self.assertEqual(draft.generated_by, "heuristic-template")
        self.assertIn("Jane Doe", draft.body)
