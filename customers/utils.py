"""Customer grouping logic: resolve emails/domains to a single Customer record."""
import re

from django.db import transaction

from .models import Customer, CustomerEmailAlias

# Free/personal email providers never define a "company" for grouping purposes -
# two different people on gmail.com are not the same customer just because of that.
FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "live.com",
    "msn.com",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def normalize_email(email):
    return (email or "").strip().lower()


def extract_domain(email):
    email = normalize_email(email)
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1]


def is_personal_domain(domain):
    return domain in FREE_EMAIL_DOMAINS


@transaction.atomic
def get_or_create_customer_for_email(email, name=""):
    """Resolve the Customer a given email address belongs to, creating one if needed.

    Grouping rules:
    1. If an alias already exists for this exact email, reuse its customer.
    2. Otherwise, if the email's domain is a company domain (not a free/personal
       provider) and an existing customer already uses that domain, attach the
       new alias to that customer so every contact at the same company groups
       together.
    3. Otherwise create a new Customer (keyed by domain for company addresses,
       or by the individual email itself for personal addresses).
    """
    email = normalize_email(email)
    if not email:
        return None

    alias = CustomerEmailAlias.objects.select_related("customer").filter(email=email).first()
    if alias:
        return alias.customer

    domain = extract_domain(email)
    customer = None

    if domain and not is_personal_domain(domain):
        customer = Customer.objects.filter(company_domain=domain).first()

    if customer is None:
        customer = Customer.objects.create(
            name=name,
            company_domain="" if is_personal_domain(domain) else domain,
            primary_email=email,
        )
    elif name and not customer.name:
        customer.name = name
        customer.save(update_fields=["name"])

    CustomerEmailAlias.objects.get_or_create(email=email, defaults={"customer": customer})
    return customer


def group_emails_by_customer(emails):
    """Given an iterable of email addresses, return {email: Customer}."""
    return {email: get_or_create_customer_for_email(email) for email in emails}


def find_customer_by_text(text):
    """Best-effort: find the first email address mentioned in free text and
    resolve it to a Customer. Used for sources (like Google Tasks) that don't
    carry a structured sender address.
    """
    match = EMAIL_RE.search(text or "")
    if not match:
        return None
    return get_or_create_customer_for_email(match.group(0))
