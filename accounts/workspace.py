"""Google Workspace domain-wide delegation: sync Gmail + Chat for every user
in the domain via a service account impersonating each one, instead of each
rep going through the per-user OAuth consent flow.

Google Tasks has no domain-wide-delegation support at all, so it is
intentionally not covered here - Tasks always goes through the per-user
OAuth flow in accounts/services.py, regardless of whether workspace-wide
sync is enabled.
"""
import json
import logging

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


def _load_service_account_info():
    if settings.GOOGLE_SERVICE_ACCOUNT_FILE:
        try:
            with open(settings.GOOGLE_SERVICE_ACCOUNT_FILE) as handle:
                return json.load(handle)
        except (OSError, ValueError):
            logger.exception("Could not read GOOGLE_SERVICE_ACCOUNT_FILE")
            return None
    if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            return json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        except ValueError:
            logger.exception("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON")
            return None
    return None


def is_enabled():
    return bool(
        settings.USE_WORKSPACE_SYNC
        and settings.GOOGLE_WORKSPACE_DOMAIN
        and _load_service_account_info()
    )


def is_domain_email(email):
    domain = settings.GOOGLE_WORKSPACE_DOMAIN
    if not domain or not email:
        return False
    return email.strip().lower().endswith(f"@{domain.strip().lower()}")


def get_delegated_credentials(user_email, scopes=None):
    """Service-account credentials impersonating a specific Workspace user.

    Returns None if no service account key is configured.
    """
    info = _load_service_account_info()
    if not info:
        return None
    return service_account.Credentials.from_service_account_info(
        info, scopes=scopes or settings.GOOGLE_DWD_SCOPES
    ).with_subject(user_email)


def list_workspace_user_emails():
    """Enumerate active user emails in the domain via the Admin SDK Directory
    API, impersonating GOOGLE_WORKSPACE_ADMIN_EMAIL (must be a super admin,
    or a delegated admin with directory read privileges).

    Optionally narrowed with GOOGLE_WORKSPACE_QUERY, e.g. "orgUnitPath='/Sales'".
    Suspended accounts are excluded. Returns [] if not configured.
    """
    if not settings.GOOGLE_WORKSPACE_ADMIN_EMAIL:
        logger.warning("GOOGLE_WORKSPACE_ADMIN_EMAIL is not set; cannot list workspace users")
        return []

    credentials = get_delegated_credentials(
        settings.GOOGLE_WORKSPACE_ADMIN_EMAIL, scopes=settings.GOOGLE_ADMIN_DIRECTORY_SCOPES
    )
    if not credentials:
        return []

    service = build("admin", "directory_v1", credentials=credentials, cache_discovery=False)

    emails = []
    page_token = None
    while True:
        request_kwargs = {
            "domain": settings.GOOGLE_WORKSPACE_DOMAIN,
            "maxResults": 200,
            "pageToken": page_token,
        }
        if settings.GOOGLE_WORKSPACE_QUERY:
            request_kwargs["query"] = settings.GOOGLE_WORKSPACE_QUERY

        response = service.users().list(**request_kwargs).execute()
        for entry in response.get("users", []):
            if entry.get("suspended"):
                continue
            email = entry.get("primaryEmail")
            if email:
                emails.append(email)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return emails
