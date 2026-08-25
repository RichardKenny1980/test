"""Thin wrapper around the Google Calendar API returning normalized dicts."""
import datetime

from django.utils import timezone
from googleapiclient.discovery import build

# Attendees who responded this way aren't going, so their events shouldn't
# clutter the agenda.
DECLINED = "declined"


def get_calendar_service(credentials):
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _parse_event_time(value):
    """Parse a Calendar API start/end block.

    Returns (datetime, is_all_day). Timed events carry "dateTime"; all-day
    events carry a bare "date", which is rendered as local midnight.
    """
    if not value:
        return None, False

    if value.get("dateTime"):
        raw = value["dateTime"].replace("Z", "+00:00")
        try:
            return datetime.datetime.fromisoformat(raw), False
        except ValueError:
            return None, False

    if value.get("date"):
        try:
            day = datetime.date.fromisoformat(value["date"])
        except ValueError:
            return None, True
        naive = datetime.datetime.combine(day, datetime.time.min)
        return timezone.make_aware(naive, timezone.get_current_timezone()), True

    return None, False


def _conference_url(event):
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for entry in event.get("conferenceData", {}).get("entryPoints", []) or []:
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry["uri"]
    return ""


def normalize_event(event, calendar_id):
    start, is_all_day = _parse_event_time(event.get("start"))
    end, _ = _parse_event_time(event.get("end"))

    attendees = []
    for attendee in event.get("attendees", []) or []:
        if attendee.get("resource"):
            continue  # meeting rooms, not people
        attendees.append(
            {
                "email": attendee.get("email", ""),
                "name": attendee.get("displayName", ""),
                "organizer": bool(attendee.get("organizer")),
                "response": attendee.get("responseStatus", ""),
            }
        )

    return {
        "google_event_id": event["id"],
        "calendar_id": calendar_id,
        "title": event.get("summary", ""),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "conference_url": _conference_url(event),
        "start": start,
        "end": end,
        "is_all_day": is_all_day,
        "attendees": attendees,
        "organizer_email": event.get("organizer", {}).get("email", ""),
    }


def _user_declined(event):
    for attendee in event.get("attendees", []) or []:
        if attendee.get("self") and attendee.get("responseStatus") == DECLINED:
            return True
    return False


def fetch_events(credentials, calendar_id="primary", days_ahead=1, max_results=50):
    """Fetch events from now-ish through `days_ahead` days out.

    Starts from the beginning of today so events already in progress (or
    finished earlier today) still appear on the agenda. `singleEvents`
    expands recurring series into individual instances.
    """
    service = get_calendar_service(credentials)

    now = timezone.localtime()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = start_of_day + datetime.timedelta(days=days_ahead)

    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_of_day.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        )
        .execute()
    )

    results = []
    for event in response.get("items", []):
        if event.get("status") == "cancelled" or _user_declined(event):
            continue
        normalized = normalize_event(event, calendar_id)
        if normalized["start"]:
            results.append(normalized)
    return results
