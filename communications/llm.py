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


SUMMARY_SYSTEM = """You brief a busy sales/support rep on where each customer \
account stands. The rep already knows who the customer is - they need to know \
what changed, what is being asked of them, and what is at stake.

Write the summary as 3-5 sentences of specific prose. Rules:
- Lead with the live issue or open question, not a description of the inbox.
- Name concrete specifics: amounts, dates, product names, blockers, decisions, \
who is waiting on whom.
- Never write filler like "the customer sent several messages", "there is \
ongoing correspondence", or "they are engaged". If you cannot say something \
specific, say less.
- State who owes the next move (the rep or the customer) and, when the messages \
imply a deadline, when it is due.
- Only assert what the messages and tasks actually say. If something is \
ambiguous, say it is unclear rather than guessing.

Action points are imperative, single-step, and start with a verb ("Send the \
revised SOW to Jane", "Confirm the March 14 migration window"). Include only \
what the rep must actually do next - typically 0-4 items. Return an empty list \
when nothing is genuinely outstanding; padding is worse than an empty list."""


def summarize_customer(customer_name, communications_text, tasks_text, today=""):
    """Ask Claude for a concise customer summary + action points.

    Returns a CustomerSummaryResult, or None if the call fails.
    """
    prompt = (
        f"Customer: {customer_name or 'Unknown'}\n"
        f"Today's date: {today or 'unknown'}\n\n"
        "=== Recent communications (oldest first) ===\n"
        f"{communications_text or '(none)'}\n\n"
        "=== Open tasks ===\n"
        f"{tasks_text or '(none)'}\n\n"
        "Brief the rep on this account."
    )
    try:
        response = get_client().messages.parse(
            model=settings.LLM_SUMMARY_MODEL,
            max_tokens=1024,
            system=SUMMARY_SYSTEM,
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


DRAFT_SYSTEM = """You draft email replies for a sales/support rep to review, \
edit, and send. The rep reads every draft before it goes out.

Answer the actual questions asked in the message, point by point. A reply that \
only acknowledges receipt wastes the rep's time - they can write "thanks, \
looking into it" themselves.

Rules:
- Never invent facts: no prices, dates, availability, feature promises, or \
commitments that are not in the message or clearly implied by it.
- Where a specific the rep must supply is missing, leave a short bracketed \
placeholder like [confirm delivery date] rather than guessing a value.
- Match the sender's register - warm and direct, no corporate padding. Skip \
openers like "I hope this email finds you well".
- Keep it under 150 words unless the message genuinely requires more.
- Sign off with "Best regards" and no name; the rep's signature is appended \
when they send."""


def draft_reply(sender_name, subject, message_text):
    """Ask Claude to draft a reply to a customer message.

    Returns a DraftReplyResult, or None if the call fails.
    """
    prompt = (
        "Draft a reply to this message.\n\n"
        f"From: {sender_name or 'the customer'}\n"
        f"Subject: {subject or '(no subject)'}\n"
        f"Message:\n{message_text or '(no content)'}"
    )
    try:
        response = get_client().messages.parse(
            model=settings.LLM_SUMMARY_MODEL,
            max_tokens=512,
            system=DRAFT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=DraftReplyResult,
        )
        return response.parsed_output
    except Exception:
        logger.exception("LLM draft reply generation failed; falling back to heuristics")
        return None
