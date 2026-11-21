import { api, post, escape as e, human, money, date } from "./api.js";

const put = (path, body) => api(path, {method: "PUT", body: JSON.stringify(body)});
const lines = (value) => value.split("\n").map(v => v.trim()).filter(Boolean);
const kinds = ["proposal", "brand_strategy", "content_calendar", "meeting_summary", "campaign_copy", "monthly_report"];
const qcChecks = ["aspect_ratio", "resolution", "audio_levels", "subtitles", "brand_logo", "contact_details", "spelling", "colour_consistency", "deliverables", "export_settings", "copyright", "brand_compliance"];

export function agencyTools(ui) {
  const {heading, panel, button, field, area, select, option, form, row,
    showModal, saveAndRefresh, downloadJSON, go} = ui;
  const detailView = (value) => {
    if (value === null || value === undefined) return "<span>Not supplied</span>";
    if (Array.isArray(value)) return `<ul>${value.map(v => `<li>${detailView(v)}</li>`).join("")}</ul>`;
    if (typeof value === "object") return Object.entries(value).map(([key, v]) =>
      `<div class="script-block"><h4>${e(human(key))}</h4>${detailView(v)}</div>`).join("");
    return `<span style="white-space:pre-wrap">${e(value)}</span>`;
  };

  async function page(id) {
    const [clients, projects, followups, bi] = await Promise.all([
      api("/clients"), api("/projects"), api("/sales/follow-ups"), api("/studio/business-intelligence"),
    ]);
    let html = heading("AGENCY OPERATIONS", "From first contact to delivery.",
      "Client knowledge, creative approvals, production checks and project margins.",
      button("AI business analysis", "agency-analysis") + button("+ Onboard client", "agency-client", "", "primary"));
    html += panel("Sales follow-ups", followups.length ? `<div class="table-wrap"><table><thead><tr><th>Business</th><th>Owner</th><th>Reminder</th><th>Due</th><th></th></tr></thead><tbody>${followups.map(f =>
      `<tr><td>${e(f.business_name)}</td><td>${e(f.assigned_to || "Unassigned")}</td><td>${e(f.activity)}</td><td>${date(f.due_date)}</td><td>${button("Review lead", "agency-sales", f.lead_id, "small")}</td></tr>`).join("")}</tbody></table></div>` : '<p class="panel-body">No follow-ups are due. Assign a sales owner and start date from a lead’s sales profile.</p>');
    html += panel("Business performance", `<div class="panel-body"><p>${bi.sales.total_leads} leads · ${bi.sales.deals_won} won · ${bi.sales.meetings_booked} meetings · ${bi.pending_document_reviews} documents awaiting review</p>${Object.entries(bi.finance_by_currency).map(([currency, f]) => `<p><strong>${e(currency)}</strong> · Paid invoices ${money(f.paid_invoice_value, currency)} · Costs ${money(f.total_cost, currency)} · Margin ${money(f.realized_margin, currency)} · Outstanding ${money(f.outstanding, currency)}</p>`).join("") || "<p>Add projects, invoices and expenses to track profitability.</p>"}<p class="hint">Totals use paid invoice values and recorded expenses. Currencies stay separate.</p></div>`, button("Export report", "agency-bi", "", "small"));
    html += panel("Client knowledge", clients.length ? `<div class="panel-body">${clients.map(c => `<div class="script-block"><h3>${e(c.name)}</h3><p>${e(c.onboarding.business_category)} · ${e(c.onboarding.business_location)}</p>${button("View / edit profile", "agency-edit-client", c.id, "small")}</div>`).join("")}</div>` : '<p class="panel-body">Onboard a brand, then link its profile to a project. Its knowledge will also inform generated scripts.</p>');
    html += panel("Project operations", `<div class="panel-body"><label>Choose a project<select aria-label="Choose a project" data-filter="agency-project"><option value="">Select project…</option>${projects.map(p => `<option value="${e(p.id)}" ${p.id === id ? "selected" : ""}>${e(p.name)}</option>`).join("")}</select></label></div>`);
    if (!id) return html;
    const project = projects.find(p => p.id === id);
    if (!project) return html + '<p class="notice">Project not found.</p>';
    const [docs, costs, tracker, scripts] = await Promise.all([
      api(`/projects/${id}/documents`), api(`/projects/${id}/profitability`),
      api(`/projects/${id}/production`), api(`/projects/${id}/scripts`),
    ]);
    html += panel(e(project.name), `<div class="panel-body"><p>${e(project.client_name)} · ${project.work_paused ? "Work paused" : "Active"}</p><div class="detail-actions">${button("Link client profile", "agency-link", id)}${button("Generate document", "agency-generate", id)}${button("Production & QC", "agency-production", id)}${button("Add expense", "agency-expense", id)}${button("Marketing metrics", "agency-metrics", id)}${button("Marketing report", "agency-report", id)}${button("Production brief", "agency-brief", id)}</div><p>Paid invoices ${money(costs.paid_invoice_value, costs.currency)} · Costs ${money(costs.total_cost, costs.currency)} · Margin ${money(costs.realized_margin, costs.currency)}</p><p>Production: ${e(human(tracker?.details.stage || "planning"))}</p>${scripts[0] ? button("Submit latest script for approval", "agency-script-review", `${id}|${scripts[0].id}`) : '<p class="hint">Generate or import a script in Projects before submitting it for approval.</p>'}</div>`);
    html += panel("Document versions & approvals", docs.length ? `<div class="table-wrap"><table><thead><tr><th>Document</th><th>Version</th><th>Status</th><th>Actions</th></tr></thead><tbody>${docs.map(d => `<tr><td>${e(human(d.kind))}</td><td>${d.version}</td><td>${e(human(d.status))}</td><td>${button("Read", "agency-document", `${id}|${d.id}`, "small")} ${["draft", "director_approved"].includes(d.status) ? button("Review", "agency-review", `${d.id}|${d.status}`, "small") : ""}${d.status === "approved" ? button("Export handoff", "agency-handoff", d.id, "small") : ""}</td></tr>`).join("")}</tbody></table></div>` : '<p class="panel-body">Generate a draft to begin. Director review comes before the client decision.</p>');
    return html;
  }

  function clientForm(existing) {
    const data = existing?.onboarding || {};
    const textFields = [["Brand name", "name"], ["Business category", "business_category"], ["Business location", "business_location"], ["Tone of voice", "tone_of_voice"]];
    const listFields = [["Brand objectives", "brand_objectives"], ["Competitors", "competitors"], ["Marketing channels", "marketing_channels"], ["Products / services", "products"], ["KPIs", "kpis"], ["Preferred languages", "preferred_languages"], ["Approved brand facts", "approved_facts"], ["Brand asset URLs", "asset_urls"], ["Previous campaigns", "previous_campaigns"]];
    showModal(existing ? "Edit client knowledge" : "Client onboarding", form(
      textFields.map(([label, key]) => field(label, key, {value: data[key] || ""})).join("") +
      area("Target audience", "target_audience") + area("Brand guidelines", "brand_guidelines", "Brand promises, visual rules, claims to avoid") +
      listFields.map(([label, key]) => area(label + " (one per line)", key, "", ["brand_objectives", "kpis", "preferred_languages"].includes(key))).join("") +
      row(field("Monthly marketing budget", "monthly_budget", {type: "number", min: 0, step: ".01", value: data.monthly_budget || 0}), field("Currency", "currency", {value: data.currency || "INR"})), "Save client"), async values => {
        const body = {...values};
        for (const [, key] of listFields) body[key] = lines(values[key]);
        if (existing) await put(`/clients/${existing.id}`, body); else await post("/clients", body);
        await saveAndRefresh("Client knowledge saved.");
      });
    for (const key of ["target_audience", "brand_guidelines", ...listFields.map(([, key]) => key)]) {
      const node = document.querySelector(`#modal-body [name="${key}"]`);
      node.value = Array.isArray(data[key]) ? data[key].join("\n") : (data[key] || "");
    }
  }

  const actions = {
    "agency-client": () => clientForm(),
    "agency-edit-client": async id => clientForm(await api(`/clients/${id}`)),
    "agency-bi": async () => downloadJSON(await api("/studio/business-intelligence"), "studio-business-report.json"),
    "agency-analysis": async () => showModal("Business analysis · internal draft", detailView((await post("/studio/business-analysis")).analysis)),
    "agency-link": async id => {
      const clients = await api("/clients");
      if (!clients.length) throw new Error("Onboard a client first.");
      showModal("Link client knowledge", form(select("Client", "client_id", clients.map(c => option(c.id, c.name)).join("")), "Link client"), async data => {
        await put(`/projects/${id}/client/${data.client_id}`, {});
        await saveAndRefresh("Client knowledge linked to project.");
      });
    },
    "agency-generate": id => showModal("Generate a creative draft", form(
      select("Document type", "kind", kinds.map(k => option(k, human(k))).join("")) +
      area("Instructions / contracted deliverables", "instructions") +
      row(field("Calendar start date", "start_date", {type: "date", required: false}), field("Calendar deliverables", "deliverable_count", {type: "number", min: 1, max: 60, value: 26})) +
      field("Monthly report through date (uses calendar start as report start)", "end_date", {type: "date", required: false}) +
      area("Meeting transcript (for meeting summary)", "transcript", "", false), "Generate draft", "AI generation uses your configured provider. Every version starts a new review."), async data => {
        await post(`/projects/${id}/documents/${data.kind}`, {instructions: data.instructions, start_date: data.start_date || null, end_date: data.end_date || null, deliverable_count: Number(data.deliverable_count), transcript: data.transcript || null});
        await saveAndRefresh("Draft saved for review.");
      }),
    "agency-document": async value => {
      const [id, documentId] = value.split("|");
      const doc = (await api(`/projects/${id}/documents`)).find(d => d.id === documentId);
      if (!doc) throw new Error("Document not found.");
      showModal(`${human(doc.kind)} · version ${doc.version}`, `<div class="notice">${e(human(doc.status))}</div>${detailView(doc.output)}<h3>Review history</h3>${detailView(doc.reviews)}`);
    },
    "agency-review": value => {
      const [id, status] = value.split("|");
      const stage = status === "draft" ? "director" : "client";
      showModal(`Record ${stage} decision`, form(select("Decision", "decision", option("approved", "Approve") + option("rejected", "Reject")) + field("Reviewed by", "reviewed_by") + area("Decision note", "note"), "Record decision", "Record the actual human decision. A newer version supersedes earlier approvals."), async data => {
        await post(`/agency/documents/${id}/review`, {...data, stage});
        await saveAndRefresh("Review recorded.");
      });
    },
    "agency-handoff": async id => downloadJSON(await api(`/agency/documents/${id}/handoff`), "approved-handoff.json"),
    "agency-script-review": async value => {
      const [project, script] = value.split("|");
      await post(`/projects/${project}/scripts/${script}/submit-review`);
      await saveAndRefresh("Script submitted for director review.");
    },
    "agency-brief": async id => showModal("Approved production brief", detailView(await api(`/projects/${id}/production-brief`))),
    "agency-production": async id => {
      const saved = (await api(`/projects/${id}/production`))?.details || {};
      showModal("Production tracker & final QC", form(
        select("Stage", "stage", ["planning", "shooting", "editing", "qc", "ready", "delivered"].map(v => `<option ${saved.stage === v ? "selected" : ""} value="${v}">${human(v)}</option>`).join("")) +
        ["crew", "equipment", "props", "costumes"].map(k => area(human(k) + " (one per line)", k, "", false)).join("") +
        `<div class="agency-checks">${["backup_primary_verified", "backup_secondary_verified", ...qcChecks].map(k => `<label><input type="checkbox" name="${k}" ${(saved[k] || saved.qc?.[k]) ? "checked" : ""}> ${e(human(k))}</label>`).join("")}</div>` +
        field("Final approved by", "final_approved_by", {required: false, value: saved.final_approved_by || ""}) + area("Notes", "notes", "", false), "Save production", "Ready/delivered requires an approved script, both backups, every QC check and final human approval."), async data => {
          const body = {stage: data.stage, final_approved_by: data.final_approved_by || null, notes: data.notes || null, qc: {}};
          for (const k of ["crew", "equipment", "props", "costumes"]) body[k] = lines(data[k]);
          for (const k of ["backup_primary_verified", "backup_secondary_verified"]) body[k] = data[k] === "on";
          for (const k of qcChecks) body.qc[k] = data[k] === "on";
          await put(`/projects/${id}/production`, body);
          await saveAndRefresh("Production checks saved.");
        });
      for (const k of ["crew", "equipment", "props", "costumes", "notes"]) document.querySelector(`#modal-body [name="${k}"]`).value = Array.isArray(saved[k]) ? saved[k].join("\n") : saved[k] || "";
    },
    "agency-expense": id => showModal("Record a project expense", form(field("Expense reference", "external_id") + select("Category", "category", ["production", "advertising", "operating"].map(k => option(k, human(k))).join("")) + field("Description", "description") + row(field("Amount (project currency)", "amount", {type:"number", min: ".01", step: ".01"}), field("Incurred on", "incurred_on", {type:"date"})) + field("Recorded by", "recorded_by"), "Record expense"), async data => {
      await post(`/projects/${id}/expenses`, data);
      await saveAndRefresh("Expense recorded.");
    }),
    "agency-metrics": id => showModal("Import daily campaign metrics", form(field("Platform", "platform", {value:"meta"}) + field("Campaign ID", "campaign_id") + field("Reporting day", "day", {type:"date"}) + ["impressions", "reach", "clicks", "leads", "conversions", "published_content", "engagements", "audience_growth"].map(k => field(human(k), k, {type:"number", ...(k === "audience_growth" ? {} : {min:0}), value:0})).join("") + row(field("Spend (project currency)", "spend", {type:"number", min:0, step:".01", value:0}), field("Attributed revenue (if known)", "attributed_revenue", {type:"number", min:0, step:".01", required:false})), "Save metrics", "One record per campaign, platform and day. Reimporting replaces that day’s values."), async data => {
      const {platform, campaign_id, day, ...metrics} = data;
      for (const key in metrics) metrics[key] = metrics[key] === "" ? null : Number(metrics[key]);
      await put(`/projects/${id}/marketing-metrics`, {platform, campaign_id, day, metrics});
      await saveAndRefresh("Campaign metrics saved.");
    }),
    "agency-report": id => showModal("Marketing report", form(row(field("From", "start", {type:"date"}), field("Through", "end", {type:"date"})), "View report"), async data => {
      const report = await api(`/projects/${id}/marketing-report?${new URLSearchParams(data)}`);
      showModal("Campaign performance", detailView(report));
    }),
    "agency-sales": async id => {
      const [lead, sales] = await Promise.all([api(`/leads/${id}`), api(`/leads/${id}/sales`)]);
      const saved = sales.profile || {};
      const history = sales.history.filter(h => h.status.startsWith("outreach_")).map(h => `<div class="script-block"><p>${e(human(h.status))} · ${date(h.occurred_at)}</p>${button("Read draft / review", "agency-outreach-review", `${id}|${h.id}`, "small")}</div>`).join("");
      showModal(`Sales · ${lead.business_name}`, `<div class="notice">${lead.opted_out ? "Opted out · follow-ups stopped" : saved.stopped_reason ? `Follow-ups stopped: ${e(saved.stopped_reason)}` : "Follow-up reminders require human-reviewed outreach."}</div>${saved.intelligence ? detailView(saved.intelligence) : ""}<div class="detail-actions">${button("Analyze lead", "agency-score", id)}${button("Prepare outreach draft", "agency-outreach", id)}${button("Record sales activity", "agency-sales-event", id)}</div>${history}` + form(field("Assigned salesperson", "assigned_to", {required:false, value:saved.assigned_to || ""}) + field("Industry", "industry", {required:false, value:saved.industry || ""}) + field("Follow-up start (day 1)", "follow_up_start", {type:"date", required:false, value:saved.follow_up_start || ""}), "Save sales profile"), async data => {
        await put(`/leads/${id}/sales`, Object.fromEntries(Object.entries(data).map(([k,v]) => [k, v || null])));
        await saveAndRefresh("Sales profile saved.");
      });
    },
    "agency-score": async id => {
      await post(`/leads/${id}/intelligence`);
      await actions["agency-sales"](id);
    },
    "agency-outreach": async id => {
      await post(`/leads/${id}/outreach-draft`);
      await actions["agency-sales"](id);
    },
    "agency-outreach-review": async value => {
      const [leadId, draftId] = value.split("|");
      const draft = (await api(`/leads/${leadId}/sales`)).history.find(h => h.id === draftId);
      if (!draft) throw new Error("Draft not found.");
      showModal("Outreach draft", detailView(draft.details.output) + (draft.status === "outreach_draft" ? form(select("Decision", "decision", option("approved", "Approve draft") + option("rejected", "Reject draft")) + field("Reviewed by", "reviewed_by") + area("Decision note", "note"), "Record review", "Approval records a decision. Delivery and WhatsApp opt-in checks remain in your messaging workflow.") : detailView(draft.details.review)), async data => {
        await post(`/leads/${leadId}/outreach/${draftId}/review`, {...data, stage:"director"});
        await saveAndRefresh("Outreach draft reviewed.");
      });
    },
    "agency-sales-event": id => showModal("Record sales activity", form(field("Event reference", "event_id", {value:crypto.randomUUID()}) + select("Activity", "event", ["responded", "declined", "contacted", "meeting_booked", "follow_up_completed"].map(k => option(k, human(k))).join("")) + select("Channel", "channel", ["manual", "email", "whatsapp", "phone", "meeting"].map(k => option(k,k)).join("")) + select("Follow-up milestone (completion only)", "milestone", option("none", "Not a completion") + [1,3,5,8,14].map(n => option(n, `Day ${n}`)).join("")) + area("Note", "note", "", false), "Record activity", "A response or decline permanently stops this sequence. Opt-outs are handled in Lead inbox."), async data => {
      await post(`/leads/${id}/sales-events`, {...data, milestone: data.milestone === "none" ? null : Number(data.milestone), note: data.note || null});
      await saveAndRefresh("Sales activity recorded.");
    }),
  };
  return {page, actions};
}
