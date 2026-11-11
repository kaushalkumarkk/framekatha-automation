# n8n HTTP contracts

Use `http://127.0.0.1:8000` for local n8n, or your securely reachable deployment for a
hosted instance. Configure n8n Header Auth credentials with `X-API-Key`, store the key
in n8n's credential store, and send `Content-Type: application/json`. All endpoints
below require the key. Browser session cookies are separate and not needed by n8n.
The live `/docs` page contains every request schema.

## Endpoints

| Method / path | Input / purpose |
| --- | --- |
| `POST /leads/ingest` | Master-lead ingestion and deduplication; see README example |
| `GET /leads`, `GET /leads/{id}` | Paginated/filterable leads and individual detail |
| `PATCH /leads/{id}/status` | `{"status":"qualified"}` |
| `PATCH /leads/{id}/opt-out` | `{"reason":"Requested unsubscribe"}`; never clears opt-out |
| `POST /scrapers/runs` | `{"channel":"maps"}`; optional future `scheduled_at` with timezone; returns 202 and `run_id` |
| `GET /scrapers/runs` | Latest 100 run summaries and counts |
| `POST /projects` | Project brief, client, skills, fee range and optional shoot details |
| `GET /projects`, `GET /projects/{id}` | Project records |
| `PUT /projects/{id}` | Full project input; submitted casting protects client/date/fee fields |
| `POST /talent/import` | Talent/contact/portfolio/skills/fees/availability import |
| `GET /talent?database=A`, `GET /talent/{id}` | Portfolio-based A/B filtering and detail |
| `PUT /talent/{id}` | Full talent input; update availability, blocked dates and fees |
| `POST /projects/{id}/match` | Empty body; ranked eligible talent with score and suggested fee |
| `POST /talent/{id}/negotiate` | `project_id` and full `conversation` list; bounded proposal only |
| `GET /talent/{id}/negotiations` | Persisted conversation state per project |
| `POST /projects/{id}/selections` | `talent_id`, `proposed_fee`; creates selection |
| `GET /projects/{id}/selections` | Selections joined with talent |
| `POST /projects/{id}/send-to-client` | Empty body; prepares packet for n8n to send, marks proposed selections submitted |
| `POST /projects/{id}/client-approval` | `selection_id`, `decision`, `approved_by`, optional `note` |
| `GET /projects/{id}/call-sheet` | PDF attachment, approved talent only |
| `POST /projects/{id}/script` | Optional `requirement`, `language`, `duration_seconds`, `tone`; saves new version |
| `GET /projects/{id}/script` | Latest script version including `output` |
| `GET /projects/{id}/scripts` | All saved versions, newest first |
| `POST /projects/{id}/feedback` | `{"text":"Remove scene-1"}`; review record and proposed operations |
| `GET /projects/{id}/feedback` | Review history |
| `POST /feedback/{id}/review` | `decision` approved/rejected, `reviewed_by`; never executes edits |
| `POST /invoices/evaluate` | Invoice input below; upserts reference and evaluates overdue milestone |
| `GET /invoices` | Invoice register |
| `POST /invoices/{id}/evaluate` | Empty body; reevaluates the persisted invoice |
| `PATCH /invoices/{id}/status` | `{"status":"paid"}`; evaluates after update |
| `GET /invoices/notices` | Draft/reviewed suspension notices |
| `POST /invoices/notices/{id}/review` | `decision`, `reviewed_by`; never sends |
| `POST /projects/{id}/resume` | `reviewed_by`, `note`; human payment review required |
| `GET /studio/overview` | Counts, recent projects and activity |
| `GET /studio/integrations` | Configuration booleans, never secrets |
| `GET /studio/dead-letters` | Safe failure summaries, without contact payloads |
| `POST /studio/dead-letters/{id}/resolve` | Mark reviewed failure resolved; no automatic replay |
| `GET /health/ready` | Local database readiness; `/health` alone is unauthenticated liveness |

## Example project

```json
{
  "name": "Launch Film",
  "client_name": "Example Client",
  "requirement": "A 30 second cinematic brand launch film",
  "required_skills": ["acting", "bengali"],
  "min_fee": "2000.00",
  "max_fee": "10000.00",
  "currency": "INR",
  "shoot_date": "2026-12-10",
  "call_time": "09:00",
  "location": "Kolkata studio",
  "cinematographer": "Assigned cinematographer"
}
```

Dates/names are illustrative. Use the returned project UUID in subsequent calls.

## Example negotiation

```json
{
  "project_id": "PROJECT_UUID",
  "conversation": [{"role":"user","content":"My requested fee is INR 6000."}]
}
```

Allowed roles are `user` and `assistant`. Supply the conversation so far, including
previous replies. Save/send nothing as a confirmed agreement: the result always has
`confirmed: false` and `requires_human_approval: true`. The client-approval flow is separate.

## Example invoice

```json
{
  "project_id": "PROJECT_UUID",
  "external_id": "YOUR_INVOICE_REFERENCE",
  "amount": "25000.00",
  "due_date": "2026-11-01",
  "status": "unpaid"
}
```

The client name and currency come from the project. Statuses: unpaid, paid, cancelled,
disputed. Once a reference exists, changing its project, amount or due date is rejected.
Use the returned `action_key` to deduplicate reminder milestones. Recheck opt-outs
before outreach, and invoice status before notice delivery. Approving a notice does not send it.

## Error and retry handling

Success codes vary: 200 for most actions, 201 for newly saved resources, 202 for queued
runs. Handle 401 as credential failure; 404 as missing record; 409 as conflict/approval
order/human review; 422 as invalid input or rejected model output; 502 as failed provider
work; 503 as missing configuration, queue unavailability, or database outage. Every
response carries `X-Request-ID` for correlation.

Lead ingestion supports stable payload `idempotency_key` values. Invoice external IDs
and notice uniqueness prevent duplicate records. **Other POSTs are not globally
idempotent**: script retries can save extra versions and run retries can queue extra
jobs. Retain returned IDs, inspect state after a network timeout, and avoid blind retries
on approval/submission/create endpoints. Provider retries are already bounded. n8n owns
delivery retries, CRM reminders, social scheduling, official WhatsApp templates, and
unsubscribe enforcement; this backend sends no outbound messages.
