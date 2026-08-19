# Personal Assistant Tool

A Django web app that aggregates a rep's Gmail, Google Chat (Spaces), and
Google Tasks activity, groups it by customer, and surfaces summaries,
urgent items, and draft replies on a single auto-refreshing dashboard.

## Architecture

| App             | Responsibility |
|------------------|----------------|
| `accounts`       | Google OAuth2 login/consent flow, encrypted-at-rest token storage/refresh, and optional Workspace domain-wide delegation (service-account impersonation + Admin SDK directory discovery). |
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

`communications/summarizer.py` handles urgency flagging, customer
summaries, and draft replies. It runs on deterministic, offline heuristics
(keyword matching + extractive summaries) by default, so the pipeline
needs no external LLM call and is fully unit-testable with no API key.

Setting `ANTHROPIC_API_KEY` switches it to Claude (`communications/llm.py`):
**Claude Sonnet 5** writes the customer summaries and draft replies (these
get read by a human, so quality matters), and **Claude Haiku 4.5** does the
urgency classification pass (cheap and fast, since it runs on every synced
message/task). Every LLM call returns `None` on any failure - missing key,
network error, bad response - and `summarizer.py` transparently falls back
to the heuristic for that item, so a flaky API never breaks a sync run.
Models are configurable via `LLM_SUMMARY_MODEL` / `LLM_URGENCY_MODEL`.

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

### Google Workspace domain-wide delegation (optional)

If you're on Google Workspace, you can skip the per-rep OAuth click for
Gmail + Chat entirely: a service account impersonates every user in the
domain instead. Google Tasks has no domain-wide-delegation support, so it
always uses the per-user OAuth flow above regardless of this setting.

1. In Cloud Console, create a **service account** and download its JSON key.
2. In the **Workspace Admin console** → Security → API controls →
   Domain-wide delegation, authorize the service account's **Client ID**
   for these scopes:
   `gmail.readonly`, `chat.spaces.readonly`, `chat.messages.readonly`,
   `admin.directory.user.readonly` (the last one is only needed to
   enumerate domain users).
3. Set `GOOGLE_SERVICE_ACCOUNT_FILE` (path to the key) or
   `GOOGLE_SERVICE_ACCOUNT_JSON` (the key inline), `GOOGLE_WORKSPACE_DOMAIN`,
   and `GOOGLE_WORKSPACE_ADMIN_EMAIL` (a super admin, or an admin with
   directory-read privileges - used only to list users, never to read
   their mail) in `.env`.
4. Optionally set `GOOGLE_WORKSPACE_QUERY` to restrict discovery to an OU
   or group, e.g. `orgUnitPath='/Sales'`, instead of the whole domain.

When enabled, `accounts.tasks.sync_workspace_directory` discovers every
active (non-suspended) user in scope via the Admin SDK Directory API and
syncs Gmail + Chat for each of them automatically - `communications.tasks.
sync_all_communications` (the per-user-OAuth fan-out) steps aside to avoid
double-syncing the same users. This is a real access-model change, not
just config: it grants org-wide mail/chat read access via one shared key
rather than per-person opt-in consent, so it's worth confirming with
whoever owns IT/security policy before enabling it in production - and the
service account key itself should be treated as a high-value secret.

### Background workers

```bash
# Terminal 1: Redis (broker/result backend)
redis-server

# Terminal 2: Celery worker
celery -A assistant_project worker -l info

# Terminal 3: Celery beat (periodic sync schedule)
celery -A assistant_project beat -l info
```

The beat schedule syncs Gmail, Chat, and Google Tasks every 30 minutes,
and refreshes cached customer summaries every 30 minutes as well.

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
summary/draft generation (both the heuristic path and the Claude-backed
path, with the Anthropic client mocked), and the Celery sync tasks with
the Gmail/Chat/Tasks API clients mocked out. No live network calls.
