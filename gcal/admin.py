from django.contrib import admin

from .models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ("title", "customer", "start", "end", "is_all_day", "user")
    list_filter = ("is_all_day",)
    search_fields = ("title", "description", "location", "organizer_email")
