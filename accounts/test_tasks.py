from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from . import tasks

User = get_user_model()


class SyncWorkspaceDirectoryTests(TestCase):
    @patch("accounts.workspace.is_enabled", return_value=False)
    @patch("accounts.workspace.list_workspace_user_emails")
    def test_skips_when_not_enabled(self, mock_list_emails, mock_is_enabled):
        count = tasks.sync_workspace_directory()

        self.assertEqual(count, 0)
        mock_list_emails.assert_not_called()

    @patch("communications.tasks.sync_chat_for_user.delay")
    @patch("communications.tasks.sync_gmail_for_user.delay")
    @patch("accounts.workspace.list_workspace_user_emails")
    @patch("accounts.workspace.is_enabled", return_value=True)
    def test_creates_users_and_fans_out_sync(
        self, mock_is_enabled, mock_list_emails, mock_gmail_delay, mock_chat_delay
    ):
        mock_list_emails.return_value = ["jane@acmecorp.com", "bob@acmecorp.com"]

        count = tasks.sync_workspace_directory()

        self.assertEqual(count, 2)
        self.assertEqual(User.objects.filter(username="jane@acmecorp.com").count(), 1)
        self.assertEqual(User.objects.filter(username="bob@acmecorp.com").count(), 1)
        self.assertEqual(mock_gmail_delay.call_count, 2)
        self.assertEqual(mock_chat_delay.call_count, 2)

    @patch("communications.tasks.sync_chat_for_user.delay")
    @patch("communications.tasks.sync_gmail_for_user.delay")
    @patch("accounts.workspace.list_workspace_user_emails")
    @patch("accounts.workspace.is_enabled", return_value=True)
    def test_reuses_existing_user_for_already_connected_rep(
        self, mock_is_enabled, mock_list_emails, mock_gmail_delay, mock_chat_delay
    ):
        existing = User.objects.create_user(username="jane@acmecorp.com", email="jane@acmecorp.com")
        mock_list_emails.return_value = ["jane@acmecorp.com"]

        tasks.sync_workspace_directory()

        self.assertEqual(User.objects.filter(username="jane@acmecorp.com").count(), 1)
        mock_gmail_delay.assert_called_once_with(existing.id)
