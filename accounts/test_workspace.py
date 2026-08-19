from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from . import workspace


@override_settings(
    USE_WORKSPACE_SYNC=True,
    GOOGLE_WORKSPACE_DOMAIN="acmecorp.com",
    GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", "client_email": "svc@acmecorp.iam.gserviceaccount.com"}',
    GOOGLE_SERVICE_ACCOUNT_FILE="",
)
class IsEnabledTests(TestCase):
    def test_enabled_with_domain_and_key(self):
        self.assertTrue(workspace.is_enabled())

    @override_settings(GOOGLE_WORKSPACE_DOMAIN="")
    def test_disabled_without_domain(self):
        self.assertFalse(workspace.is_enabled())

    @override_settings(USE_WORKSPACE_SYNC=False)
    def test_disabled_when_flag_off(self):
        self.assertFalse(workspace.is_enabled())

    @override_settings(GOOGLE_SERVICE_ACCOUNT_JSON="")
    def test_disabled_without_key(self):
        self.assertFalse(workspace.is_enabled())

    @override_settings(GOOGLE_SERVICE_ACCOUNT_JSON="not valid json")
    def test_disabled_with_malformed_json(self):
        self.assertFalse(workspace.is_enabled())


@override_settings(GOOGLE_WORKSPACE_DOMAIN="acmecorp.com")
class IsDomainEmailTests(TestCase):
    def test_matches_domain(self):
        self.assertTrue(workspace.is_domain_email("jane@acmecorp.com"))

    def test_case_insensitive(self):
        self.assertTrue(workspace.is_domain_email("Jane@AcmeCorp.com"))

    def test_rejects_other_domain(self):
        self.assertFalse(workspace.is_domain_email("jane@othercorp.com"))

    def test_rejects_empty_email(self):
        self.assertFalse(workspace.is_domain_email(""))

    @override_settings(GOOGLE_WORKSPACE_DOMAIN="")
    def test_rejects_when_no_domain_configured(self):
        self.assertFalse(workspace.is_domain_email("jane@acmecorp.com"))


@override_settings(
    GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account"}',
    GOOGLE_SERVICE_ACCOUNT_FILE="",
)
class GetDelegatedCredentialsTests(TestCase):
    @patch("accounts.workspace.service_account.Credentials.from_service_account_info")
    def test_impersonates_requested_user(self, mock_from_info):
        mock_creds = MagicMock()
        mock_from_info.return_value.with_subject.return_value = mock_creds

        result = workspace.get_delegated_credentials("jane@acmecorp.com", scopes=["scope-a"])

        mock_from_info.assert_called_once_with({"type": "service_account"}, scopes=["scope-a"])
        mock_from_info.return_value.with_subject.assert_called_once_with("jane@acmecorp.com")
        self.assertEqual(result, mock_creds)

    @override_settings(GOOGLE_SERVICE_ACCOUNT_JSON="")
    def test_returns_none_without_service_account(self):
        self.assertIsNone(workspace.get_delegated_credentials("jane@acmecorp.com"))


@override_settings(
    USE_WORKSPACE_SYNC=True,
    GOOGLE_WORKSPACE_DOMAIN="acmecorp.com",
    GOOGLE_WORKSPACE_ADMIN_EMAIL="admin@acmecorp.com",
    GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account"}',
    GOOGLE_SERVICE_ACCOUNT_FILE="",
    GOOGLE_WORKSPACE_QUERY="",
)
class ListWorkspaceUserEmailsTests(TestCase):
    def test_returns_empty_without_admin_email(self):
        with override_settings(GOOGLE_WORKSPACE_ADMIN_EMAIL=""):
            self.assertEqual(workspace.list_workspace_user_emails(), [])

    @patch("accounts.workspace.build")
    @patch("accounts.workspace.get_delegated_credentials")
    def test_filters_suspended_and_paginates(self, mock_get_creds, mock_build):
        mock_get_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        page_one = {
            "users": [
                {"primaryEmail": "jane@acmecorp.com", "suspended": False},
                {"primaryEmail": "suspended@acmecorp.com", "suspended": True},
            ],
            "nextPageToken": "page-2",
        }
        page_two = {
            "users": [{"primaryEmail": "bob@acmecorp.com", "suspended": False}],
        }
        mock_service.users.return_value.list.return_value.execute.side_effect = [page_one, page_two]

        emails = workspace.list_workspace_user_emails()

        self.assertEqual(emails, ["jane@acmecorp.com", "bob@acmecorp.com"])
        self.assertEqual(mock_service.users.return_value.list.call_count, 2)

    @patch("accounts.workspace.build")
    @patch("accounts.workspace.get_delegated_credentials")
    def test_returns_empty_when_no_delegated_credentials(self, mock_get_creds, mock_build):
        mock_get_creds.return_value = None

        self.assertEqual(workspace.list_workspace_user_emails(), [])
        mock_build.assert_not_called()
