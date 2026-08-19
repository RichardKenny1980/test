import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from .models import GoogleCredential
from .services import get_credentials, get_gmail_chat_credentials, get_or_create_local_user, save_credentials

User = get_user_model()


class SaveCredentialsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    def _fake_credentials(self, refresh_token="refresh-1"):
        creds = MagicMock()
        creds.token = "access-1"
        creds.refresh_token = refresh_token
        creds.token_uri = "https://oauth2.googleapis.com/token"
        creds.client_id = "client-id"
        creds.client_secret = "client-secret"
        creds.scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        creds.expiry = timezone.now() + datetime.timedelta(hours=1)
        return creds

    def test_creates_credential_record(self):
        save_credentials(self.user, self._fake_credentials(), google_email="rep@example.com")

        stored = GoogleCredential.objects.get(user=self.user)
        self.assertEqual(stored.access_token, "access-1")
        self.assertEqual(stored.refresh_token, "refresh-1")
        self.assertEqual(stored.google_email, "rep@example.com")

    def test_tokens_are_encrypted_at_rest(self):
        save_credentials(self.user, self._fake_credentials())

        # Bypass the ORM's field conversion (which would transparently decrypt)
        # and read the literal column value straight from the database.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token FROM accounts_googlecredential WHERE user_id = %s",
                [self.user.pk],
            )
            raw_value = cursor.fetchone()[0]

        self.assertNotEqual(raw_value, "access-1")
        # But the model API transparently decrypts it back.
        self.assertEqual(GoogleCredential.objects.get(user=self.user).access_token, "access-1")

    def test_missing_refresh_token_preserves_existing_one(self):
        save_credentials(self.user, self._fake_credentials(refresh_token="refresh-1"))
        save_credentials(self.user, self._fake_credentials(refresh_token=None))

        stored = GoogleCredential.objects.get(user=self.user)
        self.assertEqual(stored.refresh_token, "refresh-1")
        self.assertEqual(stored.access_token, "access-1")


class GetCredentialsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep@example.com")

    def test_returns_none_without_stored_credentials(self):
        self.assertIsNone(get_credentials(self.user))

    @patch("accounts.services.Request")
    @patch("accounts.services.Credentials")
    def test_refreshes_expired_credentials(self, mock_credentials_cls, mock_request_cls):
        GoogleCredential.objects.create(
            user=self.user,
            access_token="old-access",
            refresh_token="refresh-1",
            client_id="client-id",
            client_secret="client-secret",
            scopes=["scope-a"],
            expiry=timezone.now() - datetime.timedelta(hours=1),
        )

        mock_instance = MagicMock()
        mock_instance.expired = True
        mock_instance.refresh_token = "refresh-1"
        mock_instance.token = "new-access"
        mock_instance.token_uri = "https://oauth2.googleapis.com/token"
        mock_instance.client_id = "client-id"
        mock_instance.client_secret = "client-secret"
        mock_instance.scopes = ["scope-a"]
        mock_instance.expiry = timezone.now() + datetime.timedelta(hours=1)
        mock_credentials_cls.return_value = mock_instance

        result = get_credentials(self.user)

        mock_instance.refresh.assert_called_once()
        self.assertEqual(result, mock_instance)
        self.assertEqual(GoogleCredential.objects.get(user=self.user).access_token, "new-access")

    @patch("accounts.services.Credentials")
    def test_does_not_refresh_when_not_expired(self, mock_credentials_cls):
        GoogleCredential.objects.create(
            user=self.user,
            access_token="access-1",
            refresh_token="refresh-1",
            client_id="client-id",
            client_secret="client-secret",
            scopes=["scope-a"],
            expiry=timezone.now() + datetime.timedelta(hours=1),
        )

        mock_instance = MagicMock()
        mock_instance.expired = False
        mock_credentials_cls.return_value = mock_instance

        get_credentials(self.user)

        mock_instance.refresh.assert_not_called()


class GetOrCreateLocalUserTests(TestCase):
    def test_creates_user_keyed_by_email(self):
        user = get_or_create_local_user("jane@acmecorp.com")

        self.assertEqual(user.username, "jane@acmecorp.com")
        self.assertEqual(user.email, "jane@acmecorp.com")

    def test_reuses_existing_user(self):
        first = get_or_create_local_user("jane@acmecorp.com")
        second = get_or_create_local_user("jane@acmecorp.com")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(User.objects.filter(username="jane@acmecorp.com").count(), 1)


class GetGmailChatCredentialsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jane@acmecorp.com", email="jane@acmecorp.com")

    @patch("accounts.workspace.get_delegated_credentials")
    @patch("accounts.workspace.is_domain_email", return_value=True)
    @patch("accounts.workspace.is_enabled", return_value=True)
    @patch("accounts.services.get_credentials")
    def test_prefers_delegated_credentials_for_domain_user(
        self, mock_get_credentials, mock_is_enabled, mock_is_domain_email, mock_get_delegated
    ):
        delegated = MagicMock()
        mock_get_delegated.return_value = delegated

        result = get_gmail_chat_credentials(self.user)

        self.assertEqual(result, delegated)
        mock_get_credentials.assert_not_called()

    @patch("accounts.workspace.get_delegated_credentials")
    @patch("accounts.workspace.is_enabled", return_value=False)
    @patch("accounts.services.get_credentials")
    def test_falls_back_to_oauth_when_workspace_sync_disabled(
        self, mock_get_credentials, mock_is_enabled, mock_get_delegated
    ):
        mock_get_credentials.return_value = "oauth-creds"

        result = get_gmail_chat_credentials(self.user)

        self.assertEqual(result, "oauth-creds")
        mock_get_delegated.assert_not_called()

    @patch("accounts.workspace.get_delegated_credentials")
    @patch("accounts.workspace.is_domain_email", return_value=False)
    @patch("accounts.workspace.is_enabled", return_value=True)
    @patch("accounts.services.get_credentials")
    def test_falls_back_to_oauth_for_user_outside_delegated_domain(
        self, mock_get_credentials, mock_is_enabled, mock_is_domain_email, mock_get_delegated
    ):
        mock_get_credentials.return_value = "oauth-creds"

        result = get_gmail_chat_credentials(self.user)

        self.assertEqual(result, "oauth-creds")
        mock_get_delegated.assert_not_called()
