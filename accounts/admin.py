from django.contrib import admin

from .models import GoogleCredential


@admin.register(GoogleCredential)
class GoogleCredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "google_email", "expiry", "updated_at")
    readonly_fields = ("access_token", "refresh_token", "client_id", "client_secret")
    search_fields = ("user__username", "google_email")
