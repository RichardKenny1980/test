"""Summarization, urgency flagging, and draft-reply generation.

Each public function here is LLM-backed (via ``communications.llm``, Claude
Sonnet 5 / Haiku 4.5) when ``USE_LLM`` is configured, and falls back to
lightweight, deterministic heuristics (keyword matching + extractive
summaries) otherwise - including when the LLM call itself fails. This keeps
the pipeline usable offline/in CI with no API key, and resilient to
transient API errors in production.
"""
from django.utils import timezone

from . import llm

URGENT_KEYWORDS = [
    "urgent",
    "asap",
    "immediately",
    "critical",
    "emergency",
    "deadline",
    "overdue",
    "escalate",
    "high priority",
    "important",
    "action required",
    "time-sensitive",
    "time sensitive",
]


def detect_urgency(text):
    """Return (is_urgent, reason) based on simple keyword heuristics."""
    lowered = (text or "").lower()
    for keyword in URGENT_KEYWORDS:
        if keyword in lowered:
            return True, f"Contains urgency keyword: '{keyword}'"
    return False, ""


def _classify_urgency(text):
    """LLM urgency classification when enabled, heuristic fallback otherwise."""
    if llm.is_enabled():
        result = llm.classify_urgency(text)
        if result is not None:
            return result
    return detect_urgency(text)


def flag_communication(communication):
    """Update and persist a CommunicationLog's urgency flag from its content."""
    text = " ".join([communication.subject or "", communication.snippet or "", communication.body_text or ""])
    is_urgent, reason = _classify_urgency(text)
    if is_urgent != communication.is_urgent or reason != communication.urgency_reason:
        communication.is_urgent = is_urgent
        communication.urgency_reason = reason
        communication.save(update_fields=["is_urgent", "urgency_reason"])
    return is_urgent


def flag_task(task):
    """Update and persist a TaskItem's urgency flag from its content and due date."""
    text = " ".join([task.title or "", task.notes or ""])
    keyword_urgent, _ = _classify_urgency(text)
    is_overdue = bool(task.due and task.due < timezone.now() and task.status != task.STATUS_COMPLETED)
    urgent = keyword_urgent or is_overdue
    if urgent != task.is_urgent:
        task.is_urgent = urgent
        task.save(update_fields=["is_urgent"])
    return urgent


def _heuristic_summary(recent_communications, open_tasks, urgent_comms, urgent_tasks):
    lines = []
    if recent_communications:
        lines.append(f"{len(recent_communications)} recent message(s):")
        for comm in recent_communications:
            label = comm.subject or (comm.snippet[:60] if comm.snippet else "(no subject)")
            lines.append(f"  - [{comm.get_source_display()}] {label} ({comm.sender_email or 'unknown sender'})")
    else:
        lines.append("No recent communications.")

    if open_tasks:
        lines.append(f"{len(open_tasks)} open task(s):")
        for task in open_tasks:
            due = task.due.strftime("%Y-%m-%d") if task.due else "no due date"
            lines.append(f"  - {task.title} (due {due})")

    action_points = []
    for comm in urgent_comms:
        label = comm.subject or (comm.snippet[:60] if comm.snippet else "(no subject)")
        action_points.append(f"Urgent: {label} — {comm.urgency_reason}")
    for task in urgent_tasks:
        action_points.append(f"Urgent task: {task.title}")

    return "\n".join(lines), action_points


def _communications_as_text(communications):
    lines = []
    for comm in communications:
        label = comm.subject or (comm.snippet[:60] if comm.snippet else "(no subject)")
        lines.append(f"- [{comm.get_source_display()}] {label} ({comm.sender_email or 'unknown sender'})")
    return "\n".join(lines)


def _tasks_as_text(tasks):
    lines = []
    for task in tasks:
        due = task.due.strftime("%Y-%m-%d") if task.due else "no due date"
        lines.append(f"- {task.title} (due {due})")
    return "\n".join(lines)


def build_customer_summary(customer, communication_limit=5, task_limit=5):
    """Regenerate and persist the cached CustomerSummary for one customer."""
    from .models import CustomerSummary

    recent_communications = list(customer.communications.order_by("-occurred_at")[:communication_limit])
    open_tasks = list(customer.tasks.exclude(status="completed").order_by("due")[:task_limit])
    urgent_comms = list(customer.communications.filter(is_urgent=True))
    urgent_tasks = list(customer.tasks.filter(is_urgent=True).exclude(status="completed"))

    summary_text, action_points = _heuristic_summary(
        recent_communications, open_tasks, urgent_comms, urgent_tasks
    )

    if llm.is_enabled():
        llm_result = llm.summarize_customer(
            str(customer),
            _communications_as_text(recent_communications),
            _tasks_as_text(open_tasks),
        )
        if llm_result is not None:
            summary_text = llm_result.summary
            action_points = list(llm_result.action_points)

    summary, _ = CustomerSummary.objects.update_or_create(
        customer=customer,
        defaults={
            "summary_text": summary_text,
            "action_points": action_points,
            "urgent_count": len(urgent_comms) + len(urgent_tasks),
        },
    )
    return summary


DRAFT_TEMPLATE = (
    "Hi {name},\n\n"
    "Thank you for your message{subject_clause}. {reference_clause}\n\n"
    "I'm reviewing this and will follow up shortly with next steps. "
    "In the meantime, please let me know if there's anything urgent I should prioritize.\n\n"
    "Best regards"
)


def _display_name(communication):
    if communication.sender_name:
        return communication.sender_name
    if communication.sender_email:
        return communication.sender_email.split("@")[0]
    return "there"


def _heuristic_draft(communication):
    subject_clause = f' about "{communication.subject}"' if communication.subject else ""
    reference_clause = (
        f'You mentioned: "{communication.snippet[:150]}"' if communication.snippet else ""
    )
    body = DRAFT_TEMPLATE.format(
        name=_display_name(communication),
        subject_clause=subject_clause,
        reference_clause=reference_clause,
    ).strip()
    subject = f"Re: {communication.subject}" if communication.subject else "Re: your message"
    return subject, body


def generate_draft_reply(communication):
    """Create (or update) a draft reply for a communication."""
    from .models import Draft

    subject, body, generated_by = None, None, "heuristic-template"

    if llm.is_enabled():
        llm_result = llm.draft_reply(
            _display_name(communication),
            communication.subject,
            communication.body_text or communication.snippet,
        )
        if llm_result is not None:
            subject = llm_result.subject or (
                f"Re: {communication.subject}" if communication.subject else "Re: your message"
            )
            body = llm_result.body
            generated_by = "claude"

    if body is None:
        subject, body = _heuristic_draft(communication)

    draft, _ = Draft.objects.update_or_create(
        customer=communication.customer,
        communication=communication,
        status=Draft.STATUS_DRAFT,
        defaults={
            "subject": subject,
            "body": body,
            "generated_by": generated_by,
        },
    )
    return draft
