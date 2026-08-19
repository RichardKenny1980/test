import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assistant_project.settings")

app = Celery("assistant_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Discovers every active user in the Workspace domain (via the service
    # account + Admin SDK Directory API) and fans out Gmail/Chat sync for
    # each. No-op unless GOOGLE_SERVICE_ACCOUNT_FILE/JSON + domain-wide
    # delegation are configured - see accounts/workspace.py.
    "sync-workspace-directory-every-30-minutes": {
        "task": "accounts.tasks.sync_workspace_directory",
        "schedule": crontab(minute="*/30"),
    },
    # Gmail/Chat sync for individually-connected (per-user OAuth) users.
    # Skipped automatically when workspace-wide sync above is enabled, to
    # avoid double-syncing the same domain users.
    "sync-gmail-and-chat-every-30-minutes": {
        "task": "communications.tasks.sync_all_communications",
        "schedule": crontab(minute="*/30"),
    },
    # Google Tasks has no domain-wide-delegation support, so this always
    # covers Tasks via the per-user OAuth flow regardless of the above.
    "sync-google-tasks-every-30-minutes": {
        "task": "gtasks.tasks.sync_all_tasks",
        "schedule": crontab(minute="*/30"),
    },
    "refresh-customer-summaries-every-30-minutes": {
        "task": "communications.tasks.refresh_all_customer_summaries",
        "schedule": crontab(minute="*/30"),
    },
}
