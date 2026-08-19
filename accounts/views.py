from django.conf import settings
from django.contrib.auth import login as auth_login
from django.shortcuts import redirect
from django.urls import reverse

from .services import build_flow, get_or_create_local_user, save_credentials


def google_login(request):
    """Kick off the Google OAuth2 consent flow."""
    flow = build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    request.session["google_oauth_state"] = state
    return redirect(authorization_url)


def google_callback(request):
    """Handle Google's OAuth2 redirect: exchange the code, store tokens."""
    state = request.session.get("google_oauth_state")
    flow = build_flow(state=state)
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials

    google_email = _extract_email(credentials)

    if request.user.is_authenticated:
        user = request.user
    elif google_email:
        user = get_or_create_local_user(google_email)
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    else:
        return redirect(reverse("dashboard:index"))

    save_credentials(user, credentials, google_email=google_email)
    return redirect(reverse("dashboard:index"))


def _extract_email(credentials):
    if not credentials.id_token:
        return ""
    try:
        import google.auth.transport.requests as google_requests
        import google.oauth2.id_token as google_id_token

        id_info = google_id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
        return id_info.get("email", "")
    except Exception:
        return ""
