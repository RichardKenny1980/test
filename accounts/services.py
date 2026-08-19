"""Google OAuth2 flow helpers and credential persistence/refresh logic."""
from django.conf import settings
from django.contrib.auth import get_user_model
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from .models import GoogleCredential

User = get_user_model()


def get_or_create_local_user(email):
    """Get or create the Django User for a Google account email.

    Shared by the OAuth callback (a rep connecting their own account) and
    the workspace directory sync (discovering every user in the domain) so
    both paths key users the same way.
    """
    user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
    return user


def _client_config():
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }


def build_flow(state=None):
    return Flow.from_client_config(
        _client_config(),
        scopes=settings.GOOGLE_OAUTH_SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


def save_credentials(user, credentials, google_email=""):
    """Persist (or update) a user's Google OAuth credentials.

    Google only returns a refresh_token on the first consent grant, so an
    existing refresh_token is preserved when a later response omits one.
    """
    existing = GoogleCredential.objects.filter(user=user).first()
    refresh_token = credentials.refresh_token or (existing.refresh_token if existing else "")

    defaults = {
        "access_token": credentials.token,
        "refresh_token": refresh_token,
        "token_uri": credentials.token_uri or "https://oauth2.googleapis.com/token",
        "client_id": credentials.client_id or settings.GOOGLE_CLIENT_ID,
        "client_secret": credentials.client_secret or settings.GOOGLE_CLIENT_SECRET,
        "scopes": list(credentials.scopes or settings.GOOGLE_OAUTH_SCOPES),
        "expiry": credentials.expiry,
    }
    if google_email:
        defaults["google_email"] = google_email

    obj, _ = GoogleCredential.objects.update_or_create(user=user, defaults=defaults)
    return obj


def get_credentials(user):
    """Return live google.oauth2.credentials.Credentials for a user, refreshing if expired.

    Returns None if the user has no stored Google credentials.
    """
    try:
        stored = user.google_credential
    except GoogleCredential.DoesNotExist:
        return None

    credentials = Credentials(
        token=stored.access_token,
        refresh_token=stored.refresh_token or None,
        token_uri=stored.token_uri,
        client_id=stored.client_id,
        client_secret=stored.client_secret,
        scopes=stored.scopes,
    )
    credentials.expiry = stored.expiry

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(user, credentials, google_email=stored.google_email)

    return credentials


def get_gmail_chat_credentials(user):
    """Credentials for Gmail/Chat API calls.

    Prefers workspace-wide domain delegation when it's configured and the
    user's email falls in the delegated domain (no stored tokens, no
    refresh needed - the service account key is the credential). Falls back
    to the user's individually-connected OAuth credentials otherwise.
    """
    from . import workspace

    if user.email and workspace.is_enabled() and workspace.is_domain_email(user.email):
        delegated = workspace.get_delegated_credentials(user.email, settings.GOOGLE_DWD_SCOPES)
        if delegated:
            return delegated

    return get_credentials(user)
