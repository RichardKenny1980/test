"""Thin wrapper around the Gmail API returning plain, normalized dicts."""
import base64
from email.utils import parseaddr, parsedate_to_datetime

from django.utils import timezone
from googleapiclient.discovery import build


def get_gmail_service(credentials):
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _get_header(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _decode(data):
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_body(payload):
    if payload.get("body", {}).get("data"):
        return _decode(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return _decode(part["body"]["data"])
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


def _parse_occurred_at(date_header):
    if not date_header:
        return timezone.now()
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return timezone.now()
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed)
    return parsed


def fetch_recent_messages(credentials, max_results=25, query="newer_than:7d"):
    """Fetch recent Gmail messages, normalized into a list of dicts."""
    service = get_gmail_service(credentials)
    response = service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
    message_ids = [m["id"] for m in response.get("messages", [])]

    results = []
    for message_id in message_ids:
        full = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        results.append(normalize_message(full))
    return results


def normalize_message(full):
    payload = full.get("payload", {})
    headers = payload.get("headers", [])
    sender_name, sender_email = parseaddr(_get_header(headers, "From"))

    return {
        "external_id": full["id"],
        "thread_id": full.get("threadId", ""),
        "sender_email": sender_email,
        "sender_name": sender_name,
        "subject": _get_header(headers, "Subject"),
        "snippet": full.get("snippet", ""),
        "body_text": _extract_body(payload),
        "occurred_at": _parse_occurred_at(_get_header(headers, "Date")),
        "raw_payload": {"labelIds": full.get("labelIds", [])},
    }
