from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from . import llm


class IsEnabledTests(TestCase):
    @override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
    def test_enabled_with_key_and_flag(self):
        self.assertTrue(llm.is_enabled())

    @override_settings(USE_LLM=True, ANTHROPIC_API_KEY="")
    def test_disabled_without_key_even_if_flag_set(self):
        self.assertFalse(llm.is_enabled())

    @override_settings(USE_LLM=False, ANTHROPIC_API_KEY="test-key")
    def test_disabled_when_flag_off(self):
        self.assertFalse(llm.is_enabled())


@override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
class ClassifyUrgencyTests(TestCase):
    def setUp(self):
        llm._client = None

    def tearDown(self):
        llm._client = None

    def test_empty_text_short_circuits_without_calling_api(self):
        with patch("communications.llm.get_client") as mock_get_client:
            result = llm.classify_urgency("")
        mock_get_client.assert_not_called()
        self.assertEqual(result, (False, ""))

    @patch("communications.llm.get_client")
    def test_parses_successful_response(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_output = llm.UrgencyResult(is_urgent=True, reason="Customer threatened to churn")
        mock_client.messages.parse.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = llm.classify_urgency("We are cancelling unless this is fixed today")

        self.assertEqual(result, (True, "Customer threatened to churn"))
        mock_client.messages.parse.assert_called_once()

    @patch("communications.llm.get_client")
    def test_returns_none_on_api_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.parse.side_effect = RuntimeError("boom")
        mock_get_client.return_value = mock_client

        result = llm.classify_urgency("some text")

        self.assertIsNone(result)


@override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
class SummarizeCustomerTests(TestCase):
    def setUp(self):
        llm._client = None

    def tearDown(self):
        llm._client = None

    @patch("communications.llm.get_client")
    def test_returns_parsed_summary(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_output = llm.CustomerSummaryResult(
            summary="Acme is evaluating renewal terms.",
            action_points=["Send updated pricing"],
        )
        mock_client.messages.parse.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = llm.summarize_customer("Acme Corp", "- [Gmail] Renewal question", "- Send pricing (due 2026-09-01)")

        self.assertEqual(result.summary, "Acme is evaluating renewal terms.")
        self.assertEqual(result.action_points, ["Send updated pricing"])

    @patch("communications.llm.get_client")
    def test_returns_none_on_api_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.parse.side_effect = RuntimeError("boom")
        mock_get_client.return_value = mock_client

        self.assertIsNone(llm.summarize_customer("Acme Corp", "", ""))


@override_settings(USE_LLM=True, ANTHROPIC_API_KEY="test-key")
class DraftReplyTests(TestCase):
    def setUp(self):
        llm._client = None

    def tearDown(self):
        llm._client = None

    @patch("communications.llm.get_client")
    def test_returns_parsed_draft(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_output = llm.DraftReplyResult(
            subject="Re: Contract question", body="Hi Jane, thanks for reaching out..."
        )
        mock_client.messages.parse.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = llm.draft_reply("Jane Doe", "Contract question", "Can we adjust the terms?")

        self.assertEqual(result.subject, "Re: Contract question")
        self.assertIn("Jane", result.body)

    @patch("communications.llm.get_client")
    def test_returns_none_on_api_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.parse.side_effect = RuntimeError("boom")
        mock_get_client.return_value = mock_client

        self.assertIsNone(llm.draft_reply("Jane", "Hi", "body"))
