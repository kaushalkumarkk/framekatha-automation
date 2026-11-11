# Frame Katha Studio automation

Standalone Python backend for Frame Katha Studio. **Phase 1 is implemented:** API-key
authentication, lead ingestion and deduplication, source provenance, opt-outs, audit
records, PostgreSQL migrations, and retry/dead-letter handling. Later phase folders
are placeholders. No website code, platform scraping, messaging, or AI calls run here.

Development uses a **local PostgreSQL database, without Docker**. Redis is optional
for the synchronous HTTP API and required only when running background RQ jobs.

## Local setup

Requires Python 3.11+ and `uv` (or use a standard venv and pip).

```sh
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r requirements-dev.lock
python scripts/local_db.py
```

Keep the last command running in its terminal. It runs a bundled PostgreSQL binary,
creates `framekatha` and `framekatha_test`, and writes `.env` with their connection URLs
and a generated API key **only if `.env` does not exist**. The file has owner-only
permissions. PostgreSQL listens on a local Unix socket, with TCP disabled. Data lives
in ignored `.local/postgres`; Ctrl-C stops the server and preserves the data. Restart
with the same command. This convenience runtime is for local development on supported
macOS/Linux systems, not production hosting.

In another terminal:

```sh
source .venv/bin/activate
alembic upgrade head
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

Interactive API docs: `http://127.0.0.1:8000/docs`. Use **Authorize** to enter your API
key; protected endpoints accept it in the `X-API-Key` header.
The API does not create tables at startup: run Alembic before serving requests.

### Use an existing local PostgreSQL installation

Install application dependencies with `uv pip install -e '.[dev]'`. Create separate
development and test databases, copy `.env.example` to `.env`, then set `DATABASE_URL`,
`TEST_DATABASE_URL`, and a generated `API_KEY`. Use the SQLAlchemy driver prefix
`postgresql+psycopg://`. Database credentials may be omitted when local peer/trust
authentication is configured; otherwise put credentials only in `.env`.

```sh
createdb framekatha
createdb framekatha_test
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Then run the migrations and API commands above. An existing `.env` is never rewritten
by the bundled-server helper. Set its URLs yourself if switching database servers.

## Configuration

| Variable | Purpose / default |
| --- | --- |
| `API_KEY` | Required, at least 24 characters; shared with n8n through its credentials store |
| `DATABASE_URL` | Required local PostgreSQL connection; example in `.env.example` |
| `TEST_DATABASE_URL` | Dedicated PostgreSQL test database; test schemas are created and removed here |
| `REDIS_URL` | Background queue connection; `redis://localhost:6379/0` |
| `DEFAULT_PHONE_REGION` | Phone country fallback; `IN` |
| `FUZZY_NAME_THRESHOLD` | RapidFuzz ratio threshold, 0–100; `92` |
| `INGEST_MAX_ATTEMPTS` | Maximum database attempts, 1–10; `3` |
| `RETRY_BASE_SECONDS` | Exponential backoff base; `0.25` |
| `LOG_LEVEL` | JSON log level; `INFO` |
| `APP_ENV` | Environment label; `development` |

Secrets and local data are gitignored. Anthropic, scraper, and messaging credentials
will be introduced only with their corresponding phases. Production PostgreSQL
connections can use Supabase's connection URL with `postgresql+psycopg://` and TLS
options; use a migration-capable connection for Alembic. Never expose this service
publicly without HTTPS and network access controls. The API key grants backend-wide
access; this is an n8n service API, not browser authentication or a multi-tenant API.

## n8n HTTP integration

Use an HTTP Request node with the base URL reachable from n8n. For local n8n this is
`http://127.0.0.1:8000`; hosted n8n needs a securely reachable deployment. Store the
key as an n8n Header Auth credential named `X-API-Key`, never directly in workflows.
Send JSON with `Content-Type: application/json`.

| Method / path | JSON body or query | Result |
| --- | --- | --- |
| `POST /leads/ingest` | Ingest payload below | `outcome: created` or `merged`, and master `lead` |
| `GET /leads/{id}` | None | Lead, all contact identities, and source references |
| `GET /leads` | Optional `status`, `channel`, `limit` (1–100), `offset` | `items`, `total`, `limit`, `offset` |
| `PATCH /leads/{id}/status` | `{"status":"qualified"}` | Updated lead; changes audited in `outreach_logs` |
| `PATCH /leads/{id}/opt-out` | `{"reason":"Requested unsubscribe"}` | Permanently sets the opt-out flag through this API |
| `GET /health` | None; no authentication | Process liveness |
| `GET /health/ready` | None; API key required | Database connectivity |

Example ingest body (names and identifiers are illustrative; use actual contact data
from your authorized source):

```json
{
  "business_name": "Example Production House",
  "channel": "maps",
  "external_id": "listing-reference",
  "idempotency_key": "maps:listings:listing-reference:event-001",
  "city": "Kolkata",
  "locality": "Newtown",
  "website": "https://example.com",
  "source_url": "https://example.com/listing",
  "opted_out": false,
  "metadata": {"no_website": false, "weak_seo": true}
}
```

`business_name` and `channel` are required. Optional `phone` must be a valid number;
optional `email` must be a valid full address. Channels use lowercase letters,
numbers, `_`, or `-`. Unknown top-level fields are rejected; put channel-specific
fields in `metadata`. Supply a stable, globally unique `idempotency_key` for every
source event. Reuse it with the exact same payload on retries. A changed event gets
a new key. `(channel, external_id)` identifies a listing across repeated observations.

Responses use HTTP 200 for successful creation and merging, 401 for failed auth,
404 for missing leads, 422 for invalid input, 409 for human review, and 503 for
unavailable ingestion/database service. Every response has an `X-Request-ID`.
Configure bounded n8n retries for 503/network errors using the same event key.
Route 409 responses to a human review workflow; do not blindly retry them.

## Deduplication and merge behavior

* Phones normalize to E.164, with India as the default. Extensions and invalid
  numbers are rejected. Full email addresses normalize case-insensitively;
  sharing a domain never establishes identity.
* Exact phone, email, or existing source references take priority. When these point
  to different masters, ingestion rolls back and creates a dead letter for review.
* Without an exact match, normalized names use RapidFuzz's full-string ratio.
  Conflicting known cities/localities exclude candidates. Missing location values
  do not rule them out. Multiple candidates above the threshold require review.
* Existing populated master fields win, missing values are filled, and every distinct
  phone/email is retained in `lead_identities`. A later hit can match an older contact.
* Source events retain channel, listing URL, payload, and timestamps. Repeated listing
  observations without an event key update that source's latest payload and hit count.
  Distinct event keys create separate references; the original listing row owns its
  unique external ID, with later references retaining the external ID in their payload.
* Opt-out is sticky. A true flag from any source sets the master flag. Ingestion and
  the opt-out endpoint cannot clear it. There is no automated re-subscribe flow.
* PostgreSQL serializes ingestion transactions using an advisory lock, with unique
  constraints as a second line of defense. All ingestion writers must use this service.
  Connection establishment and ingestion lock waits have five-second timeouts.
  Name comparison currently scans candidates; this favors correctness at Phase 1
  volumes and should be indexed/partitioned before high-volume deployment.

Fuzzy matching is a heuristic: it cannot guarantee real-world identity when names,
contacts, or geography are missing or wrong. It may need human correction. Ambiguous
inputs create no new lead, and exact contact conflicts never silently combine masters.

Statuses: `new`, `qualified`, `contacted`, `won`, `lost`, `archived`. There is no implicit
status change during ingestion. `outreach_logs` currently audits status changes and
opt-outs; provider delivery ingestion and messaging workflows belong to later work.

## Background jobs, retries, and review

HTTP ingestion is synchronous: its response means the transaction committed. Install
and start Redis locally if you want to use the RQ entry point. Start a worker from the
repository root with the venv active:

```sh
rq worker --url redis://localhost:6379/0 leads
```

For another Python process, use `leads.jobs.enqueue_ingestion(payload)`; it returns an
RQ job ID. Queue and HTTP ingestion use the same transactional deduplication pipeline.
The producer validates the schema before enqueueing. Database connection, deadlock,
and serialization failures receive bounded exponential retries. Review conflicts and
exhausted/unexpected failures are recorded in `dead_letters`; failed RQ jobs also stay
in RQ's failed registry for seven days. No automatic replay of review conflicts occurs.

Inspect pending dead letters in your local SQL client:

```sql
SELECT id, request_id, error_code, attempt_count, created_at
FROM dead_letters WHERE status = 'pending' ORDER BY created_at;
```

Review the stored payload under appropriate access controls, correct the source data,
and resubmit through the ingest endpoint. After resolving the issue, an operator can
mark the row `resolved` and set `resolved_at` in SQL. A review UI and master-merging UI
are outside Phase 1. If PostgreSQL itself is unavailable, it cannot store a dead letter;
the service emits `dead_letter_storage_unavailable` and returns 503. n8n must retain
the event, or RQ retains the failed job, for recovery.

## Tests and checks

With local PostgreSQL running and `TEST_DATABASE_URL` set in `.env`:

```sh
pytest -q
ruff check .
ruff format --check .
alembic check
```

Tests create random isolated schemas in the dedicated test database and remove them
afterward. They cover normalization, shared-domain separation, fuzzy matching, merge
preservation, ambiguous/conflicting identities, source replay protection, sticky
opt-outs, API auth/filtering/audits, job entry points, failure retries, concurrent
phone/name ingestion, and migration upgrade/downgrade. With no `TEST_DATABASE_URL`,
unit/API tests fall back to in-memory SQLite; PostgreSQL-specific tests are skipped.
PostgreSQL tests are the acceptance check for concurrency and migrations.

## Logging and workflow boundaries

JSON logs include request IDs, event names, lead IDs, outcomes, and retry attempts.
Application logs omit payloads, contact values, API keys, and raw database exceptions.
Validation responses also omit submitted values. Source/dead-letter tables contain
contact data by design: restrict database access and retention. Run Uvicorn with
`--no-access-log` as above to avoid framework logging of query strings.

n8n must check `opted_out` immediately before outreach. WhatsApp must use approved
templates through an official provider. No bulk cold-DM automation or login-based
scraping is implemented. Future Resolve automation will produce a rough assembly for
a human editor; edit feedback and suspension notices will require human review.
