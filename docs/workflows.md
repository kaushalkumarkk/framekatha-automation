# Workflow setup and implementation limits

## Discovery

Install Chromium with `playwright install chromium`. Configure permitted source URLs
and Kolkata locations in `scrapers/locations.yaml`. Templates support `{location}` and
`{category}`. Empty source lists need configuration; they do not provide ready-made
access to third-party directories. The `maps` identifier is the business-listing channel.

The business adapter extracts public Schema.org JSON-LD and checks the business's own
website for missing title, description, and H1. SEO flags are simple heuristics, not a
search-ranking audit. Blocked/unreachable websites report SEO as unknown.

Google Maps content harvesting is excluded because general content export conflicts
with the requested platform-rule compliance; see the [Google Maps Platform terms](https://cloud.google.com/maps-platform/terms).
Use directory data you have permission to collect, or authorized manual imports.

MagicBricks/99acres adapters conservatively parse structured data. They require explicit
owner evidence and a recent `datePosted`. A Person record alone is not owner proof.
Missing evidence is skipped. Markup changes require fixture/parser updates; there is no
claim that every current listing page exposes those fields. Robots denial, unverified
robots rules, login redirects, and access challenges stop collection. No CAPTCHA or
login bypass exists. No live property-site scraping was used in tests. Social and
Upwork/LinkedIn adapters are intentionally disabled stubs.

Radar uses [News API Everything](https://newsapi.org/docs/endpoints/everything), then
sends article titles/descriptions to Claude. Only high-confidence classifications of
new podcasts by notable people become leads. Configure both provider keys and confirm
your provider plan permits the intended use.

Direct runs need no Redis. Queued or scheduled runs require a local Redis server and RQ:

```sh
redis-server --bind 127.0.0.1
# separate terminal:
rq worker --url redis://localhost:6379/0 --with-scheduler scrapers leads
```

Install Redis with your OS package manager first. On macOS, select
`--worker-class rq.worker.SpawnWorker` if fork-related library errors occur. Let n8n's
schedule trigger call the run endpoint for recurring jobs. A crashed/killed worker's
job remains in RQ's failed registry; inspect and reconcile a stale `running` run before
retrying. Failed collector/queue operations record dead letters where PostgreSQL is reachable.

## Talent and production

Database A has a portfolio URL; Database B does not. Imports merge exact contact or
portfolio identities. Explicit talent edits can update fees, blocked dates, availability,
and contacts. Different currencies are not converted. Matching excludes unavailable,
over-budget or wrong-currency talent and ranks skill overlap first. The project fee
range is **per talent**, not a total project budget.

Claude returns a proposed amount and internal rationale. The server rejects amounts
outside project bounds and constructs its own non-binding reply. Conversations are
stored, but the service never confirms or sends a fee or booking. n8n may trigger human-
reviewed email/approved WhatsApp templates. Instagram DMs are not implemented.

Select talent → prepare client packet → send it through n8n → record the actual client
decision → download a PDF call sheet. The submission endpoint returns a packet and
records submission; it does not deliver a message. The client decision is recorded by
studio staff/n8n, not by a public client portal. Client details, shoot date and fee range
are fixed after casting submission to protect approval records. Call sheets require
approved talent, shoot date, location, call time, and cinematographer. The PDF uses
ReportLab standard fonts; non-Latin names may require a production font customization.

Scripts use versioned prompt files and locally validated tool output from the
[Claude Messages API](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview).
Every generation saves a new version and brief snapshot. Shot numbers and runtime are
validated. Prompts can be reviewed in `ai/prompts/`. Scripts and music suggestions remain
creative drafts; a human chooses properly licensed music and approves the production.

## Editing

The separate [Resolve package](../resolve/README.md) runs on the editing machine,
transcribes local/Drive-synced files with Whisper, and writes a rough-cut plan. A manual
assemble command builds a new Resolve timeline and optionally queues a render. It
does not start rendering, upload footage, or promise a finished edit. Missing/visual-only
shots stay in the plan for manual selection. Real Studio/codec/LUT behavior must be
verified on the editing workstation; automated tests use a fake SDK.

Text or locally transcribed voice feedback becomes proposed trim/remove/music/colour
operations. The backend stores the review state; approval **never auto-applies** edits.
Unclear instructions produce clarification questions rather than invented targets.

## Invoicing

Days overdue are calendar days after `due_date`, using Asia/Kolkata's current date.
Days 1–4 return a gentle reminder, 5–9 a follow-up, 10–14 a final reminder, and 15+
pause the project and create one draft notice. Responses include a stable `action_key`;
n8n must deduplicate actions by that key to avoid repeated reminders. Disputed invoices
route to a human and do not create automatic suspension notices. Paid/cancelled invoices
produce no reminder. Ingestion cannot silently reopen a settled invoice.

Notices require review and are never sent by this service. Before delivering an approved
notice through n8n, recheck payment status and project pause state. Recording payment
does not resume work automatically. The explicit resume endpoint requires a reviewer
and note and refuses when any unpaid/disputed invoice is 15+ days overdue. `work_paused`
is an operational flag; n8n and the human editor must honor it. The local Resolve package
does not remotely enforce a backend pause.

## Verification boundaries

PostgreSQL and Chromium workflows are tested locally. No real Anthropic/News API spend,
live property collection, Redis worker execution, Whisper model inference, or Resolve
Studio execution is represented as verified. Configure these dependencies before live
use; missing configuration fails explicitly. Do not treat fixture-backed tests as a
claim of external-platform availability.
