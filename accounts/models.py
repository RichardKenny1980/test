from django.conf import settings
from django.db import models

from .fields import EncryptedTextField


class GoogleCredential(models.Model):
    """OAuth2 credentials for a Django user's connected Google account.

    Access/refresh tokens and client secret are stored encrypted at rest via
    EncryptedTextField; only decrypted in memory when building API clients.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_credential"
    )
    google_email = models.EmailField(blank=True)
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField(blank=True)
    token_uri = models.CharField(max_length=255, default="https://oauth2.googleapis.com/token")
    client_id = EncryptedTextField()
    client_secret = EncryptedTextField()
    scopes = models.JSONField(default=list, blank=True)
    expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Google credential for {self.user} ({self.google_email})"
