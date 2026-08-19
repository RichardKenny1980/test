from django.contrib import admin

from .models import CommunicationLog, CustomerSummary, Draft


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ("source", "customer", "sender_email", "subject", "is_urgent", "occurred_at")
    list_filter = ("source", "is_urgent")
    search_fields = ("subject", "sender_email", "snippet")


@admin.register(CustomerSummary)
class CustomerSummaryAdmin(admin.ModelAdmin):
    list_display = ("customer", "urgent_count", "updated_at")


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = ("customer", "subject", "status", "created_at")
    list_filter = ("status",)
