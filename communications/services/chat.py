"""Thin wrapper around the Google Chat API (Spaces) returning normalized dicts."""
from django.utils import timezone
from googleapiclient.discovery import build


def get_chat_service(credentials):
    return build("chat", "v1", credentials=credentials, cache_discovery=False)


def _parse_create_time(create_time):
    if not create_time:
        return timezone.now()
    try:
        return timezone.datetime.fromisoformat(create_time.replace("Z", "+00:00"))
    except ValueError:
        return timezone.now()


def normalize_message(message, space_name, display_name):
    sender = message.get("sender", {})
    return {
        "external_id": message.get("name", ""),
        "thread_id": message.get("thread", {}).get("name", space_name),
        "sender_email": sender.get("email", ""),
        "sender_name": sender.get("displayName", ""),
        "subject": display_name,
        "snippet": (message.get("text", "") or "")[:200],
        "body_text": message.get("text", ""),
        "occurred_at": _parse_create_time(message.get("createTime")),
        "raw_payload": {"space": space_name},
    }


def fetch_recent_space_messages(credentials, max_spaces=10, max_messages_per_space=20):
    """Fetch recent messages across the user's Google Chat Spaces."""
    service = get_chat_service(credentials)
    spaces_response = service.spaces().list(pageSize=max_spaces).execute()

    results = []
    for space in spaces_response.get("spaces", []):
        space_name = space.get("name", "")
        display_name = space.get("displayName", space_name)
        messages_response = (
            service.spaces()
            .messages()
            .list(parent=space_name, pageSize=max_messages_per_space, orderBy="createTime desc")
            .execute()
        )
        for message in messages_response.get("messages", []):
            results.append(normalize_message(message, space_name, display_name))
    return results
