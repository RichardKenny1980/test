# Personal Assistant Tool

A Django web app that aggregates a rep's Gmail, Google Chat (Spaces), and
Google Tasks activity, groups it by customer, and surfaces summaries,
urgent items, and draft replies on a single auto-refreshing dashboard.

## Architecture

| App             | Responsibility |
|------------------|----------------|
| `accounts`       | Google OAuth2 login/consent flow and encrypted-at-rest token storage/refresh. |
| `customers`      | `Customer` / `CustomerEmailAlias` models and the email/domain grouping logic. |
| `communications` | `CommunicationLog` (Gmail + Chat messages), `Draft`, `CustomerSummary` models; Gmail/Chat API clients; the summarization, urgency-flagging, and draft-generation heuristics; Celery sync tasks. |
| `gtasks`         | `TaskItem` model, Google Tasks API client, Celery sync task. |
| `dashboard`      | The web dashboard view/template (auto-refreshes every 30s). |

Background sync (`communications.tasks`, `gtasks.tasks`) runs on a Celery
worker + beat schedule (see `assistant_project/celery.py`) so Google API
calls never block a request.

### Customer grouping

`customers/utils.py` resolves every email address to a single `Customer`:
contacts sharing a company domain (e.g. `jane@acme.com` and `bob@acme.com`)
are grouped into one customer, while free/personal providers (Gmail,
Yahoo, etc.) are grouped per-individual instead. Google Tasks have no
structured sender, so `find_customer_by_text` best-effort matches an email
address mentioned in the task title/notes.

### Summarization & drafting

`communications/summarizer.py` implements this with deterministic,
offline heuristics (keyword matching + extractive summaries), so the
pipeline needs no external LLM call and is fully unit-testable. It's a
small, swappable module if you want to plug in an LLM later.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in FIELD_ENCRYPTION_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Generate the Fernet key used to encrypt stored OAuth tokens:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Google OAuth2 credentials

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an OAuth 2.0 Client ID (Web application).
2. Add `http://localhost:8000/accounts/google/callback/` as an authorized
   redirect URI.
3. Enable the Gmail API, Google Chat API, and Google Tasks API for the project.
4. Put the client ID/secret into `.env`.
5. Visit `/accounts/google/login/` to connect an account.

### Background workers

```bash
# Terminal 1: Redis (broker/result backend)
redis-server

# Terminal 2: Celery worker
celery -A assistant_project worker -l info

# Terminal 3: Celery beat (periodic sync schedule)
celery -A assistant_project beat -l info
```

The beat schedule pulls Gmail + Chat every 5 minutes, Google Tasks every 5
minutes, and refreshes cached customer summaries every 10 minutes.

## Dashboard

Visit `http://localhost:8000/` for the dashboard: customer cards with
cached summaries, flagged urgent action points, and recent draft replies.
The page reloads itself every 30 seconds (configurable via
`DASHBOARD_AUTO_REFRESH_SECONDS`).

## Tests

```bash
python manage.py test
```

Covers: email/domain customer-grouping rules, urgency-flagging and
summary/draft generation heuristics, and the Celery sync tasks with the
Gmail/Chat/Tasks API clients mocked out (no live network calls).
