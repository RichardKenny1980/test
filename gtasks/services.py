"""Thin wrapper around the Google Tasks API returning normalized dicts."""
from django.utils import timezone
from googleapiclient.discovery import build


def get_tasks_service(credentials):
    return build("tasks", "v1", credentials=credentials, cache_discovery=False)


def _parse_dt(value):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_task(task, task_list_id):
    return {
        "google_task_id": task["id"],
        "task_list_id": task_list_id,
        "title": task.get("title", ""),
        "notes": task.get("notes", ""),
        "status": task.get("status", "needsAction"),
        "due": _parse_dt(task.get("due")),
        "google_updated_at": _parse_dt(task.get("updated")),
    }


def fetch_all_tasks(credentials, max_lists=25, max_tasks_per_list=100):
    """Fetch every task across all of the user's Google Tasks lists."""
    service = get_tasks_service(credentials)
    task_lists_response = service.tasklists().list(maxResults=max_lists).execute()

    results = []
    for task_list in task_lists_response.get("items", []):
        list_id = task_list["id"]
        tasks_response = (
            service.tasks()
            .list(tasklist=list_id, maxResults=max_tasks_per_list, showCompleted=True, showHidden=True)
            .execute()
        )
        for task in tasks_response.get("items", []):
            results.append(normalize_task(task, list_id))
    return results
