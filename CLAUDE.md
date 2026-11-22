# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Frame Katha Studio automation: a FastAPI backend plus a buildless browser dashboard for a video studio's operations (lead ingestion/dedup, scrapers, talent casting, Claude-generated scripts, edit feedback, invoicing, agency operations). It is driven by n8n over HTTP; **this service sends no messages/emails/DMs**. See [README.md](README.md) for the full API, config table and dedup rules, and `docs/` for workflows, n8n contracts and blueprint coverage.

## Commands

Python 3.11+. Local PostgreSQL, no Docker (Redis only for background RQ jobs).

```sh
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.lock      # or: uv pip install -e '.[dev]'
python scripts/local_db.py                   # bundled Postgres + writes .env (only if absent); leave running
alembic upgrade head                         # API never creates tables at startup
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log

pytest -q                                    # all tests
pytest tests/test_ingestion.py::test_name -q # single test
ruff check . && ruff format --check .
alembic check                                # models vs migrations drift
python -m scripts.browser_qa                 # Chromium end-to-end QA (isolated schema, fake AI)
python -m scrapers CHANNEL [--enqueue]       # maps | magicbricks | acres99 | radar
rq worker --with-scheduler scrapers leads    # background jobs (needs Redis)
```

- Tests use `TEST_DATABASE_URL` (random isolated schemas, removed afterward); without it they fall back to in-memory SQLite and `@pytest.mark.postgres` tests are skipped. Postgres is the acceptance check for concurrency and migrations.
- `scripts/local_db.py` relies on Unix sockets (macOS/Linux); on Windows use an existing local PostgreSQL and set `DATABASE_URL`/`TEST_DATABASE_URL` (driver prefix `postgresql+psycopg://`) and `API_KEY` (≥24 chars) in `.env`.
- Ruff: line length 100, rules E,F,I,UP,B.

## Architecture

- `api/` — FastAPI app. `main.py` registers one router per domain (`routes/`), Pydantic request schemas in `api/schemas/`, `auth.py` for `X-API-Key` or an HttpOnly session cookie (one shared studio-wide key; no user accounts/multi-tenancy). `main.py` also holds global behavior: request-ID/logging middleware, security headers/CSP, validation errors that deliberately **omit submitted values**, `ConfigurationRequired`→503 and `ProviderUnavailable`→502 handlers.
- `core/` — settings (`config.py`, env-driven), DB session factory (`db.py`), SQLAlchemy models (`core/models/`, one module per domain), JSON logging, and `external.py` (`call_provider` wrapper + `ConfigurationRequired`/`ProviderUnavailable` used by every external call).
- `leads/` — ingestion pipeline (`ingestion.py`, `normalization.py`, `dedup.py`, `jobs.py` for RQ). Transactional, serialized with a Postgres advisory lock; exact phone/email/source match beats fuzzy name match; conflicts roll back and write a `dead_letters` row (HTTP 409). Opt-out is sticky. Idempotency via `idempotency_key`. Read the README "Deduplication" section before changing this.
- `scrapers/` — per-channel adapters over a `base.py`, configured by `scrapers/locations.yaml`; only permitted public sources, property adapters require owner evidence + recent date; social/Upwork/LinkedIn are disabled stubs. Never run on startup.
- `ai/` — Claude calls: `client.py::generate_json` forces a `submit_result` tool call and validates against a Pydantic schema in `ai/schemas.py`; supplied data is treated as untrusted. Versioned prompts live in `ai/prompts/*.v1.txt`; `feedback.py` parses voice/edit feedback into proposals.
- `invoicing/` — milestones, project pause flags, draft suspension notices (human resumption).
- `frontend/` — static `index.html` + `assets/*.js` served by FastAPI at `/` and `/assets`; no Node/npm build.
- `resolve/` — **separate package** (`framekatha-resolve` CLI, own `pyproject.toml`) that runs on the editing workstation: footage ingest, local Whisper, rough-assembly planning, DaVinci Resolve Studio adapter (tested with a fake adapter). It talks to the backend only over HTTP.
- `migrations/versions/` — Alembic migrations, one per phase (1 leads, 2 scraper runs, 3 projects/talent/negotiation, 4 scripts, 5 feedback, 6 invoices, plus script patterns and agency operations). Any model change needs a migration and must pass `alembic check`.

## Conventions worth knowing

- Human-in-the-loop is a design rule: scripts are versioned, feedback and notices need human review, approved feedback is never auto-applied, Resolve never auto-renders.
- Logs and error responses must not contain payloads, contact data, API keys or raw DB exceptions.
- New top-level packages must be added to `[tool.setuptools.packages.find]` (and package-data if they ship non-Python files) in `pyproject.toml`.
- Required env: `API_KEY`, `DATABASE_URL`; optional/feature-gated: `ANTHROPIC_API_KEY`, `NEWS_API_KEY`, `REDIS_URL`. Missing provider keys surface as 503 via `ConfigurationRequired`, not startup failures.
