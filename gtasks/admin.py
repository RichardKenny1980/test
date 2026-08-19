from django.contrib import admin

from .models import TaskItem


@admin.register(TaskItem)
class TaskItemAdmin(admin.ModelAdmin):
    list_display = ("title", "customer", "status", "due", "is_urgent")
    list_filter = ("status", "is_urgent")
    search_fields = ("title", "notes")
