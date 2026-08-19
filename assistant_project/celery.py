import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assistant_project.settings")

app = Celery("assistant_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "sync-gmail-and-chat-every-5-minutes": {
        "task": "communications.tasks.sync_all_communications",
        "schedule": crontab(minute="*/5"),
    },
    "sync-google-tasks-every-5-minutes": {
        "task": "gtasks.tasks.sync_all_tasks",
        "schedule": crontab(minute="*/5"),
    },
    "refresh-customer-summaries-every-10-minutes": {
        "task": "communications.tasks.refresh_all_customer_summaries",
        "schedule": crontab(minute="*/10"),
    },
}
