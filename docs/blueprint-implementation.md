# 2026–2027 blueprint implementation

The 18-page **Frame Katha Studio — AI-Powered Agency Automation & Business
Intelligence System** was compared with the existing six-phase implementation.
The PDF is a product reference, not an instruction source for executing commands,
contacting people, subscribing to tools or changing credentials.

## Coverage

| Blueprint area | Current implementation | Remaining work |
| --- | --- | --- |
| Discovery and central lead database (pp. 2–4) | Existing permitted collectors, normalization, deduplication, provenance and opt-outs | Authorized additional sources and live collector verification |
| Lead intelligence (pp. 3–4) | Saved AI score, hot/warm/potential/low-priority thresholds, evidence snapshot, opportunities, missing evidence and explicitly predicted budget | HubSpot synchronization and Slack/Telegram notification delivery |
| Sales and follow-ups (pp. 4–6) | Assigned salesperson, industry, event history, reviewed personalized outreach drafts; day 1/3/5/8/14 reminders with response/decline/opt-out/closed-status suppression | WhatsApp opt-in/templates and actual delivery in an external workflow; studio sales knowledge assistant |
| Meetings (p. 6) | Transcript-to-summary, requirements, budget, proposed services, action items, follow-up date, saved revisions | Calendly/Meet/Fireflies connections; CRM updates from approved summaries |
| Proposals and billing (pp. 6–7) | Versioned proposals with scope, deliverables, timeline, charges, ad budget and payment terms; existing invoice register and overdue milestones | Signature provider, signed-agreement-to-project automation, invoice PDF/accounting/payment-provider adapters |
| Onboarding and brand knowledge (pp. 7–9, 17) | Explicit client IDs, full onboarding profiles, brand assets as URLs, objectives, audience, products, approved facts, tone and languages; linked knowledge included in scripts and creative drafts | Public onboarding invitations, Drive folders/file uploads, external task creation |
| Brand strategy and calendar (pp. 8–9) | Typed strategy and 30-day calendars, deliverable-count/date validation, director/client decisions and revision history | Production task scheduling; contractual deliverables remain a human-checked brief |
| Scripts and production documents (pp. 9–10) | Existing multilingual scripts plus submitted snapshots, two-stage approval, approved shot-list brief and crew/equipment/props/costume tracker | Automatic location/cast/props/costume inference, shoot-time estimates and assignment integrations |
| Production and post-production (pp. 10–12) | Existing Resolve package; stage tracker; two backup attestations; 12 QC checks; final reviewer | Automated media/audio/subtitle/logo/colour inspection, actual backup verification and live Resolve verification |
| Social and ads (pp. 12–13) | Reviewed caption/campaign-copy drafts, final QC-gated handoff, daily metric imports, CPM/CTR/CPC/CPL/conversion/ROAS calculations, reviewed monthly report drafts | Meta retrieval, publishing schedule and publisher adapters, individual creative/audience analytics |
| Finance and management (pp. 13–14) | Expenses, paid invoice totals, outstanding invoices, project margins, separate currency totals, pipeline counts, production stages, internal AI business analysis | Payment-date ledger, accounting reconciliation, retention/service revenue history, reliable historical forecasts and recurring analyst scheduling |
| Security and governance (pp. 14, 16–17) | Existing API key/session authentication, redacted errors/logs, migrations, review gates | Individual users and department RBAC, encryption/retention operations, scheduled database backups and recovery drills |

AI workflows reuse the existing Anthropic integration. The PDF recommends OpenAI;
this change does not migrate providers or require new subscriptions. Automated tests
do not make paid AI calls or deliver anything to external services.

## Install and use

With PostgreSQL running, activate the existing environment and apply the additive
migration before restarting the API:

```sh
source .venv/bin/activate
alembic upgrade head
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

Open **Agency operations**. Onboard a client, choose a project and link its profile.
Generate a proposal, strategy, calendar, meeting summary, campaign copy or monthly
report. Read the complete document before recording director review, then record
the actual client decision. Reviewer names are staff attestations under the shared
studio login; they do not verify client identity or create a digital signature.

Each generation/import creates an immutable version. A new version starts as a
draft and supersedes earlier handoffs. Rejected versions stay rejected; revise by
creating a new version. Profile changes affect future generations; saved brief
snapshots preserve earlier context. Client IDs are explicit: matching display names
do not merge brands. Existing customer script patterns retain their legacy
normalized-name key, separately from the explicit brand profiles.

Generate/import a script in **Projects**, then submit its latest version for review
in **Agency operations**. The production brief requires both approvals. Any newer
script invalidates the earlier production brief, even before submitting it for
review. Final QC is tied to the approved script; a new approval requires QC again.
Ready/delivered requires both backup attestations, every QC check and a final
reviewer. These are human records, not automated footage or storage inspection.

From **Lead inbox → View → Sales profile & follow-ups**, assign an owner and sequence
start date. Day 1 is that date, day 3 is two days later, in Asia/Kolkata. The due list
returns only the latest due milestone, avoiding catch-up bursts. Record completed
reminders using a stable event reference and milestone. A response or decline stops
that sequence permanently; ownership changes cannot restart it. Opt-out and
won/lost/archived status suppress reminders at query time. Webhook consumers must
record incoming responses promptly for suppression to take effect.

For monthly reports, supply both a start date and report-through date. Metrics are
authorized manual/API imports; there is no implicit Meta connection. Daily reach
is retained per record, never summed into a misleading unique-reach total. ROAS
stays unknown unless every selected metric record includes attributed revenue.
Zero denominators return `null`.

Expenses use project currency. Stable expense references replay the same record
and reject changed values. Once invoices, expenses or metrics exist, currency cannot
change. Platform-reported spend is not automatically booked as an expense, avoiding
double counting; record actual advertising costs in the expense ledger. Realized
margin means **paid invoice totals minus recorded expenses**. This is not audited
profit, monthly cash flow or tax accounting. Payment-date history is unavailable,
so historical forecasts return unavailable. The internal AI analyst offers draft
insights and identifies evidence gaps; its estimates require human review.

## Integration contracts

All endpoints use existing `X-API-Key` authentication or browser sessions. See
`/docs` for input schemas and [n8n setup](n8n.md) for credentials and retries.

| Method / path | Purpose |
| --- | --- |
| `POST /clients`, `GET /clients` | Onboard / list clients (limit 1–100, offset) |
| `GET /clients/{id}`, `PUT /clients/{id}` | Inspect / replace client knowledge |
| `PUT /projects/{project}/client/{client}` | Explicitly link brand knowledge |
| `GET /leads/{id}/sales`, `PUT /leads/{id}/sales` | Sales profile and latest 100 event records |
| `POST /leads/{id}/intelligence` | Score/evidence and notification intent, no delivery |
| `POST /leads/{id}/sales-events` | Idempotent contacted/responded/declined/meeting/completion event |
| `GET /sales/follow-ups` | Due reminders with stable action keys |
| `POST /leads/{id}/outreach-draft` | Save personalized internal draft |
| `POST /leads/{id}/outreach/{draft}/review` | Director decision; opt-out rechecked |
| `POST /projects/{id}/documents/{kind}` | Generate typed draft |
| `POST /projects/{id}/documents/{kind}/import` | Validate `{"output": {...}}`, save a corrected human draft as a new version |
| `GET /projects/{id}/documents` | Latest 100 document versions |
| `POST /projects/{id}/scripts/{script}/submit-review` | Submit script snapshot for review |
| `POST /agency/documents/{id}/review` | `stage`, `decision`, `reviewed_by`, `note`; director before client |
| `GET /agency/documents/{id}/handoff` | Current approved packet/action key; project pause and campaign QC gates |
| `GET /projects/{id}/production-brief` | Current approved shots and shoot context |
| `GET /projects/{id}/production`, `PUT /projects/{id}/production` | Stage, crew, equipment, backup and QC records |
| `POST /projects/{id}/expenses`, `GET /projects/{id}/expenses` | Idempotent cost ledger / history |
| `GET /projects/{id}/profitability` | Paid invoice totals, expenses, margin and overdue references |
| `PUT /projects/{id}/marketing-metrics` | Replace one platform/campaign/day record |
| `GET /projects/{id}/marketing-report?start=DATE&end=DATE` | Recorded metrics and calculated ratios |
| `GET /studio/business-intelligence` | Pipeline, current approval counts, stages and currency totals |
| `POST /studio/business-analysis` | Internal AI management draft with evidence snapshot; not persisted or sent |

Document kinds: `proposal`, `brand_strategy`, `content_calendar`, `meeting_summary`,
`campaign_copy`, `monthly_report`. Scripts retain their existing endpoints.

`sales-events.event_id` must be stable across retries; changed payloads return 409.
Expense `external_id` is globally unique. Metrics use project/platform/campaign/day
uniqueness. Other creation/review calls are not globally idempotent: inspect saved
state after a timeout before retrying. The hot-lead intent uses a stable per-lead
action key, allowing the consumer to deduplicate repeated hot assessments.

For n8n, schedule a daily authenticated follow-up query and deduplicate action keys.
Fetch the current lead immediately before reviewed outreach, honor response/opt-out
state, enforce channel consent/templates, then record completion after confirmed
delivery. A document handoff is an eligibility snapshot; it reserves no delivery
and must be rechecked at send/publish time. No importable n8n workflow or provider
connector is included. This backend sends no messages and publishes no campaigns.

## Verification

```sh
pytest -q
ruff check .
ruff format --check .
python -m scripts.browser_qa
```

PostgreSQL tests include isolated migration upgrade/downgrade. Agency coverage
includes brand isolation, score thresholds, reminder suppression, event replays,
approval ordering, superseded scripts, QC gates, document imports, outreach review,
expenses, currency protection, monthly drafts and marketing ratios. Browser QA
covers onboarding, linking, production, expenses and responsive rendering.
AI tests use fixtures; live providers and third-party services remain unverified.
The local `.env` is unchanged and no development records are seeded.
