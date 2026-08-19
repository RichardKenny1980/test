"""Claude-backed urgency classification, customer summarization, and draft
replies. Every function here returns ``None`` on any failure (missing API
key, network error, malformed response) so callers in ``summarizer.py`` can
fall back to the offline heuristics without special-casing errors.

Model choice: Claude Sonnet 5 for summaries and draft replies (quality
matters - a rep reads these), Claude Haiku 4.5 for urgency classification
(cheap, fast, good enough for a should-a-human-look-at-this judgment). Both
are configurable via LLM_SUMMARY_MODEL / LLM_URGENCY_MODEL.
"""
import logging

from django.conf import settings
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_client = None


def is_enabled():
    return bool(getattr(settings, "USE_LLM", False) and settings.ANTHROPIC_API_KEY)


def get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


class UrgencyResult(BaseModel):
    is_urgent: bool
    reason: str


def classify_urgency(text):
    """Ask Claude whether a message/task needs the rep's attention today.

    Returns (is_urgent, reason), or None if the call fails for any reason.
    """
    if not text or not text.strip():
        return False, ""

    try:
        response = get_client().messages.parse(
            model=settings.LLM_URGENCY_MODEL,
            max_tokens=256,
            system=(
                "You triage customer communications and tasks for a sales/support "
                "rep. Decide if the item needs the rep's attention today: hard "
                "deadlines, explicit urgency language, churn risk, escalations, or "
                "overdue commitments count as urgent. Routine check-ins do not. "
                "Keep the reason to one short sentence."
            ),
            messages=[{"role": "user", "content": text[:4000]}],
            output_format=UrgencyResult,
        )
        result = response.parsed_output
        return result.is_urgent, result.reason
    except Exception:
        logger.exception("LLM urgency classification failed; falling back to heuristics")
        return None


class CustomerSummaryResult(BaseModel):
    summary: str
    action_points: list[str]


def summarize_customer(customer_name, communications_text, tasks_text):
    """Ask Claude for a concise customer summary + action points.

    Returns a CustomerSummaryResult, or None if the call fails.
    """
    prompt = (
        f"Customer: {customer_name or 'Unknown'}\n\n"
        f"Recent communications:\n{communications_text or '(none)'}\n\n"
        f"Open tasks:\n{tasks_text or '(none)'}\n\n"
        "Write a concise summary (3-5 sentences) of where things stand with this "
        "customer, and a short list of concrete action points the rep should take "
        "next. Only include action points that are genuinely actionable now; "
        "return an empty list if there are none."
    )
    try:
        response = get_client().messages.parse(
            model=settings.LLM_SUMMARY_MODEL,
            max_tokens=1024,
            system="You are a concise, accurate assistant summarizing customer activity for a busy sales/support rep.",
            messages=[{"role": "user", "content": prompt}],
            output_format=CustomerSummaryResult,
        )
        return response.parsed_output
    except Exception:
        logger.exception("LLM customer summary failed; falling back to heuristics")
        return None


class DraftReplyResult(BaseModel):
    subject: str
    body: str


def draft_reply(sender_name, subject, message_text):
    """Ask Claude to draft a reply to a customer message.

    Returns a DraftReplyResult, or None if the call fails.
    """
    prompt = (
        "Draft a short, professional reply to this message.\n\n"
        f"From: {sender_name or 'the customer'}\n"
        f"Subject: {subject or '(no subject)'}\n"
        f"Message:\n{message_text or '(no content)'}\n\n"
        "Keep the tone warm and professional. Do not invent commitments, prices, "
        "or dates that weren't mentioned. This is a draft for a human to review "
        "and edit before sending, not a final reply."
    )
    try:
        response = get_client().messages.parse(
            model=settings.LLM_SUMMARY_MODEL,
            max_tokens=512,
            system=(
                "You draft concise, professional email replies on behalf of a "
                "sales/support rep. The rep reviews and edits every draft before "
                "sending, so it's fine to leave specifics for them to fill in."
            ),
            messages=[{"role": "user", "content": prompt}],
            output_format=DraftReplyResult,
        )
        return response.parsed_output
    except Exception:
        logger.exception("LLM draft reply generation failed; falling back to heuristics")
        return None
