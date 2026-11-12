import { api, post, patch, escape as e, money, date, human } from "./api.js";

const $ = (selector, root = document) => root.querySelector(selector);
const icons = {
  overview:
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  leads:
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/><path d="M16 3a4 4 0 0 1 0 8"/>',
  projects:
    '<rect x="3" y="6" width="18" height="15" rx="2"/><path d="M8 6V3h8v3M3 11h18M10 11v3h4v-3"/>',
  talent:
    '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z"/>',
  discovery:
    '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M10 7v6M7 10h6"/>',
  edits:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4m-11-5 5 3-5 3Z"/>',
  invoices: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2ZM9 7h6M9 11h6M9 15h3"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 3 2 3-1 4 4 1 2 3 4-2 3 1 1-4 3-2-2-4-3-1-1-3Z"/>',
  script: '<path d="M6 3h9l4 4v14H6ZM15 3v5h4M9 12h7M9 16h7"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.projects}</svg>`;
const nav = [
  ["overview", "Overview"],
  ["leads", "Lead inbox"],
  ["projects", "Projects"],
  ["talent", "Talent library"],
  ["discovery", "Discovery"],
  ["edits", "Edit review"],
  ["invoices", "Invoices"],
  ["settings", "Workspace settings"],
];
const content = $("#content");
const modal = $("#modal");
let pageVersion = 0;
let toastTimer;
let currentProjects = [];
const statusColors = {
  new: "blue",
  qualified: "green",
  contacted: "amber",
  won: "green",
  lost: "red",
  archived: "",
  planning: "blue",
  awaiting_client: "amber",
  casting_reviewed: "green",
  proposed: "blue",
  sent: "amber",
  approved: "green",
  rejected: "red",
  pending: "amber",
  draft: "amber",
  paid: "green",
  unpaid: "amber",
  cancelled: "",
  disputed: "red",
  succeeded: "green",
  running: "blue",
  queued: "blue",
  failed: "red",
  blocked: "red",
  partial: "amber",
  resolved: "green",
};
const badge = (value) =>
  `<span class="badge ${statusColors[value] || ""}">${e(human(value))}</span>`;
const button = (label, action, id = "", type = "") =>
  `<button class="button ${type}" data-action="${action}" data-id="${e(id)}">${label}</button>`;
const heading = (eyebrow, title, subtitle, actions = "") =>
  `<div class="page-heading"><div><span class="eyebrow">${eyebrow}</span><h1>${title}</h1><p>${subtitle}</p></div><div class="heading-actions">${actions}</div></div>`;
const empty = (
  title,
  description,
  action = "",
  label = "Get started",
  name = "projects",
) =>
  `<div class="empty-state"><div class="empty-art">${icon(name)}</div><h3>${title}</h3><p>${description}</p>${action ? button(label, action, "", "primary") : ""}</div>`;
const panel = (title, body, action = "", subtitle = "") =>
  `<section class="panel"><div class="panel-heading"><div><h2>${title}</h2>${subtitle ? `<small>${subtitle}</small>` : ""}</div>${action}</div>${body}</section>`;
const tags = (values) =>
  `<div class="tags">${values.map((tag) => `<span class="tag">${e(tag)}</span>`).join("")}</div>`;
const initials = (name) =>
  String(name)
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
const searchbar = (placeholder, filters = "") =>
  `<div class="toolbar"><div class="search"><input type="search" data-search placeholder="${placeholder}" aria-label="${placeholder}"></div><div class="filter-group">${filters}</div></div>`;
const field = (label, name, options = {}) =>
  `<label>${label}<input name="${name}" type="${options.type || "text"}" ${options.required === false ? "" : "required"} ${options.min !== undefined ? `min="${options.min}"` : ""} ${options.max !== undefined ? `max="${options.max}"` : ""} ${options.step ? `step="${options.step}"` : ""} ${options.placeholder ? `placeholder="${e(options.placeholder)}"` : ""} ${options.value !== undefined ? `value="${e(options.value)}"` : ""} ${options.maxlength ? `maxlength="${options.maxlength}"` : ""}></label>`;
const area = (label, name, placeholder = "", required = true) =>
  `<label>${label}<textarea name="${name}" placeholder="${e(placeholder)}" ${required ? "required" : ""}></textarea></label>`;
const select = (label, name, options) =>
  `<label>${label}<select aria-label="${e(label)}" name="${name}" required>${options}</select></label>`;
const option = (value, label) =>
  `<option value="${e(value)}">${e(label)}</option>`;
const form = (body, submit = "Save", note = "") =>
  `<form>${body}${note ? `<p class="hint">${note}</p>` : ""}<p class="form-error" role="alert"></p><div class="form-actions">${button("Cancel", "close-modal")}<button type="submit" class="button primary">${submit}</button></div></form>`;
const row = (a, b) => `<div class="form-row">${a}${b}</div>`;
const splitTags = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
const compact = (data) =>
  Object.fromEntries(Object.entries(data).filter(([, value]) => value !== ""));

function toast(message, error = false) {
  clearTimeout(toastTimer);
  const node = $("#toast");
  node.textContent = message;
  node.classList.toggle("error", error);
  node.hidden = false;
  toastTimer = setTimeout(() => (node.hidden = true), 6000);
}
function showModal(title, body, submit) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = body;
  if (!modal.open) modal.showModal();
  const formNode = $("#modal-body form");
  if (submit && formNode)
    formNode.addEventListener("submit", async (event) => {
      event.preventDefault();
      const save = $("button[type=submit]", formNode);
      save.disabled = true;
      $(".form-error", formNode).textContent = "";
      try {
        await submit(Object.fromEntries(new FormData(formNode)), formNode);
      } catch (error) {
        $(".form-error", formNode).textContent = error.message;
      } finally {
        save.disabled = false;
      }
    });
}
function showWorkspace() {
  $("#login").hidden = true;
  $("#workspace").hidden = false;
}
function showLogin() {
  $("#workspace").hidden = true;
  $("#login").hidden = false;
  if (modal.open) modal.close();
}
function go(path) {
  if (location.hash === `#${path}`) navigate();
  else location.hash = path;
}

$("#navigation").innerHTML = nav
  .map(
    ([id, label], i) =>
      `${i === 7 ? '<div class="nav-divider"></div>' : ""}<a class="nav-item" href="#${id}" data-nav="${id}">${icon(id)}<span>${label}</span></a>`,
  )
  .join("");
$("#today").textContent = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Kolkata",
}).format(new Date());
$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const node = event.target,
    submit = $("button", node);
  submit.disabled = true;
  $("#login-error").textContent = "";
  try {
    await post("/auth/session", { api_key: node.elements.api_key.value });
    node.reset();
    showWorkspace();
    await navigate();
  } catch (error) {
    $("#login-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
$("#logout").addEventListener("click", async () => {
  try {
    await api("/auth/session", { method: "DELETE" });
    showLogin();
  } catch (error) {
    toast(error.message, true);
  }
});
$("#close-modal").addEventListener("click", () => modal.close());
modal.addEventListener("click", (event) => {
  if (event.target === modal) {
    const r = modal.getBoundingClientRect();
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      modal.close();
  }
});
$("#menu-toggle").addEventListener("click", () =>
  $("#sidebar").classList.toggle("open"),
);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") $("#sidebar").classList.remove("open");
});
document.addEventListener("click", (event) => {
  if (
    !event.target.closest("#sidebar") &&
    !event.target.closest("#menu-toggle")
  )
    $("#sidebar").classList.remove("open");
});
window.addEventListener("session-expired", showLogin);
window.addEventListener("hashchange", navigate);

async function overview() {
  const data = await api("/studio/overview");
  const c = data.counts;
  const metrics = [
    ["leads", "Lead inbox", c.leads, "Contacts across all your sources"],
    [
      "projects",
      "Productions",
      c.projects,
      `${c.paused} project${c.paused === 1 ? "" : "s"} paused`,
    ],
    ["talent", "Talent library", c.talent, "The people behind the frame"],
    [
      "talent",
      "Awaiting approval",
      c.pending_approvals,
      "Decisions that need a human",
    ],
  ];
  const projectRows = data.projects.length
    ? data.projects
        .map(
          (p) =>
            `<a class="project-row" href="#projects/${p.id}"><div class="project-icon">${e(initials(p.name))}</div><div class="project-info"><strong>${e(p.name)}</strong><small>${e(p.client_name)} · ${date(p.shoot_date)}</small></div>${p.work_paused ? '<span class="badge red">Work paused</span>' : badge(p.status)}<span class="muted">↗</span></a>`,
        )
        .join("")
    : empty(
        "Make room for your next story.",
        "Create a project to bring the brief, the cast, and the shoot together.",
        "new-project",
        "Create your first project",
      );
  const activity = data.activity.length
    ? `<div class="activity-list">${data.activity.map((item) => `<div class="activity-item"><span class="activity-dot">${icon(item.category === "lead" ? "leads" : item.category)}</span><p>${e(item.title)}<strong>${e(item.name)}</strong></p><time>${date(item.created_at)}</time></div>`).join("")}</div>`
    : empty(
        "A fresh slate.",
        "Your studio’s latest work will appear here as you add leads, talent, and projects.",
        "",
        "",
        "script",
      );
  return (
    heading(
      "THE BIG PICTURE",
      "A clear view of the studio.",
      "Good stories start with a little clarity. Here’s where everything stands.",
      button("↻ Refresh", "refresh") +
        button("+ New project", "new-project", "", "primary"),
    ) +
    `<div class="metric-grid">${metrics.map(([i, title, value, note]) => `<article class="metric-card"><div class="metric-top"><span>${title}</span><span class="metric-icon">${icon(i)}</span></div><strong class="metric-number">${value}</strong><span class="metric-note">${note}</span></article>`).join("")}</div>` +
    `<div class="dashboard-grid"><div>${panel("On the production board", projectRows, '<a class="button link" href="#projects">All projects ↗</a>', "From first brief to shoot day")}${panel("Your studio pipeline", `<div class="pipeline"><a class="pipeline-step" href="#leads"><span>01 · DISCOVER</span><strong>${c.leads}</strong><small>Leads in the inbox</small></a><a class="pipeline-step" href="#talent"><span>02 · CONNECT</span><strong>${c.talent}</strong><small>Talent in your library</small></a><a class="pipeline-step" href="#projects"><span>03 · CREATE</span><strong>${c.scripts}</strong><small>Production script drafts</small></a></div>`)}</div><div><div class="story-banner"><div><span class="eyebrow">FROM IDEA TO ACTION</span><h2>Less chasing.<br>More creating.</h2><p>Your next frame is waiting.</p></div><div class="banner-art" aria-hidden="true">✳</div></div>${panel("Around the studio", activity, "", "The latest additions to your workspace")}${c.dead_letters ? `<a href="#settings" class="notice warning">${c.dead_letters} failed or ambiguous event${c.dead_letters === 1 ? " needs" : "s need"} a review. Open workspace settings ↗</a>` : ""}</div></div>`
  );
}

async function leads() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const status = params.get("status") || "",
    channel = params.get("channel") || "";
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const data = await api(
    `/leads?limit=50&offset=${offset}${status ? "&status=" + encodeURIComponent(status) : ""}${channel ? "&channel=" + encodeURIComponent(channel) : ""}`,
  );
  const filters = `<select data-filter="lead-status" aria-label="Filter lead status">${option("", "All statuses")}${["new", "qualified", "contacted", "won", "lost", "archived"].map((v) => `<option ${v === status ? "selected" : ""} value="${v}">${human(v)}</option>`).join("")}</select><select data-filter="lead-channel" aria-label="Filter lead channel">${option("", "All sources")}${["manual", "maps", "magicbricks", "acres99", "radar"].map((v) => `<option ${v === channel ? "selected" : ""} value="${v}">${v === "maps" ? "Business listings" : v}</option>`).join("")}</select>`;
  const table = data.items.length
    ? `<div class="table-wrap"><table><thead><tr><th>Business / contact</th><th>Source</th><th>Location</th><th>Status</th><th>Added</th><th></th></tr></thead><tbody>${data.items.map((lead) => `<tr class="searchable"><td><strong>${e(lead.business_name)}</strong><span class="subline">${e(lead.primary_email || lead.primary_phone || "No contact details yet")}${lead.opted_out ? " · OPTED OUT" : ""}</span></td><td>${tags([...new Set(lead.sources.map((s) => s.channel))])}</td><td>${e(lead.locality || lead.city || "—")}</td><td>${badge(lead.status)}</td><td>${date(lead.created_at)}</td><td>${button("View ↗", "view-lead", lead.id, "small")}</td></tr>`).join("")}</tbody></table></div><div class="limit-note">Showing ${offset + 1}–${offset + data.items.length} of ${data.total} leads. ${offset ? button("← Previous", "lead-prev", "", "small") : ""} ${offset + data.items.length < data.total ? button("Next →", "lead-next", "", "small") : ""}</div>`
    : empty(
        "Every good project starts somewhere.",
        "Add a lead manually or configure a permitted discovery source. Duplicates are merged automatically.",
        "new-lead",
        "Add a lead",
        "leads",
      );
  return (
    heading(
      "RELATIONSHIPS, NOT SPREADSHEETS",
      "Lead inbox",
      "One home for every potential collaboration.",
      button("+ Add lead", "new-lead", "", "primary"),
    ) +
    searchbar("Search this page of leads…", filters) +
    panel(`${data.total} lead${data.total === 1 ? "" : "s"}`, table)
  );
}

async function projects() {
  currentProjects = await api("/projects");
  const cards = currentProjects.length
    ? `<div class="cards-grid">${currentProjects.map((p) => `<article class="project-card searchable">${p.work_paused ? '<span class="badge red">Work paused</span>' : badge(p.status)}<h3>${e(p.name)}</h3><small>${e(p.client_name)}</small><p>${e(p.requirement.slice(0, 140))}${p.requirement.length > 140 ? "…" : ""}</p><div class="project-meta"><span>${date(p.shoot_date)}</span><span>${money(p.max_fee, p.currency)} / talent max</span></div><div class="card-divider">${tags(p.required_skills.slice(0, 3))}<a href="#projects/${p.id}" class="button small">Open project ↗</a></div></article>`).join("")}</div>`
    : panel(
        "Production board",
        empty(
          "What are we making next?",
          "Start with a brief. Bring the right people, the script, and the shoot plan into one place.",
          "new-project",
          "Create a project",
        ),
      );
  return (
    heading(
      "THE PRODUCTION BOARD",
      "Stories in the making.",
      "A workspace for every brief, cast, and creative decision.",
      button("+ New project", "new-project", "", "primary"),
    ) +
    searchbar("Find a project…") +
    cards
  );
}

async function projectDetail(id) {
  const [p, selections, scripts] = await Promise.all([
    api(`/projects/${id}`),
    api(`/projects/${id}/selections`),
    api(`/projects/${id}/scripts`),
  ]);
  const approved = selections.filter(
    (row) => row.selection.status === "approved",
  );
  const cast = selections.length
    ? `<div class="table-wrap"><table><thead><tr><th>Talent</th><th>Proposed fee</th><th>Client decision</th><th></th></tr></thead><tbody>${selections.map(({ selection: s, talent: t }) => `<tr><td><strong>${e(t.name)}</strong><span class="subline">${e(t.skills.join(", "))}</span></td><td>${money(s.proposed_fee, p.currency)}</td><td>${badge(s.status)}${s.approved_by ? `<span class="subline">Recorded for ${e(s.approved_by)}</span>` : ""}</td><td>${s.status === "sent" ? button("Record decision", "client-decision", `${id}|${s.id}`, "small") : ""}</td></tr>`).join("")}</tbody></table></div>`
    : empty(
        "The right people make the frame.",
        "Match talent to the project’s skills, fee range, and shoot availability.",
        "match",
        id ? "Find talent" : "Find talent",
        "talent",
      ).replace('data-id=""', `data-id="${id}"`);
  const latest = scripts[0];
  const script = latest
    ? `<div class="panel-body"><div class="notice">Draft v${latest.version} · ${e(latest.prompt_version)} · ${date(latest.created_at)} · Human creative review required.</div><h3 class="section-title">${e(latest.output.title)}</h3>${latest.output.shooting_script.map((shot) => `<div class="script-block"><h4>SHOT ${shot.shot_number} · ${e(shot.scene_id)} · ${shot.duration_seconds}s</h4><p>${e(shot.visual)}</p>${shot.dialogue ? `<p><em>“${e(shot.dialogue)}”</em></p>` : ""}<small>${e(shot.camera)} · ${e(shot.audio)}</small></div>`).join("")}<div class="script-block"><h4>SCREENPLAY</h4><p>${e(latest.output.screenplay)}</p></div><div class="script-block"><h4>EDITING DIRECTION</h4><p>${e(latest.output.editing_direction.join("\n"))}</p></div><div class="script-block"><h4>MUSIC DIRECTION</h4>${latest.output.bgm_suggestions.map((m) => `<p>${e(m.mood)} · ${m.tempo_bpm} BPM · ${e(m.instrumentation)}<br><small>${e(m.licensing_note)}</small></p>`).join("")}</div>${button("Download script JSON", "download-script", id, "small")} <small class="hint">${scripts.length} saved version${scripts.length === 1 ? "" : "s"}</small></div>`
    : empty(
        "The brief becomes a story.",
        "Generate a structured first draft with a shooting script, screenplay, editing direction, and music suggestions.",
        "generate-script",
        "Generate a script",
        "script",
      ).replace('data-id=""', `data-id="${id}"`);
  return (
    heading(
      "PROJECT / " + e(p.client_name).toUpperCase(),
      e(p.name),
      e(p.requirement),
      '<a href="#projects" class="button">← Projects</a>' +
        button("Generate script", "generate-script", id, "primary"),
    ) +
    (p.work_paused
      ? `<div class="notice warning">Work is paused for this project. Review outstanding invoices before resuming. ${button("Review / resume", "resume", id, "small")}</div>`
      : "") +
    `<div class="detail-grid"><div class="detail-stat"><small>SHOOT & LOCATION</small><strong>${date(p.shoot_date, true)} · ${e(p.call_time || "Time TBD")} IST</strong><p class="hint">${e(p.location || "Location not set")} · ${e(p.cinematographer || "Cinematographer not set")}</p></div><div class="detail-stat"><small>CASTING FEE RANGE / PERSON</small><strong>${money(p.min_fee, p.currency)} – ${money(p.max_fee, p.currency)}</strong><div style="margin-top:10px">${tags(p.required_skills)}</div></div></div><div class="detail-actions">${button("Edit project", "edit-project", id)}${button("Find talent", "match", id)}${button("Prepare client packet", "send-client", id)}${approved.length ? `<a class="button" href="/projects/${id}/call-sheet" target="_blank" rel="noopener">Download call sheet ↗</a>` : ""}${button("Edit feedback", "project-feedback", id)}</div>` +
    panel(
      "The cast",
      cast,
      "",
      `${approved.length} client-approved · ${selections.length} selected`,
    ) +
    panel(
      "Production script",
      script,
      button("Customer pattern", "script-pattern", id, "small") +
        button("Import script", "import-script", id, "small") +
        (latest ? button("New version", "generate-script", id, "small") : ""),
    )
  );
}

async function talent() {
  const database =
    new URLSearchParams(location.hash.split("?")[1] || "").get("database") ||
    "";
  const people = await api(
    "/talent" + (database ? "?database=" + database : ""),
  );
  const cards = people.length
    ? `<div class="cards-grid">${people.map((t) => `<article class="talent-card searchable"><div class="talent-top"><div class="talent-avatar">${e(initials(t.name))}</div><div><h3>${e(t.name)}</h3><small>Database ${t.has_portfolio ? "A · Portfolio ready" : "B · Emerging talent"}</small></div></div>${tags(t.skills)}<p class="hint">${e(t.email || t.phone || "Portfolio contact")}<br>${Number(t.followers).toLocaleString("en-IN")} followers · ${t.available ? "Available" : "Unavailable"}${t.unavailable_dates.length ? " · " + t.unavailable_dates.length + " blocked dates" : ""}</p><div class="card-divider"><strong>${money(t.fee_rate, t.currency)}</strong>${button("Details ↗", "talent-detail", t.id, "small")}</div></article>`).join("")}</div>`
    : panel(
        "Talent library",
        empty(
          "Find your next collaborator.",
          "Build a thoughtful library of actors and models, with skills, portfolios, availability, and fees.",
          "new-talent",
          "Add talent",
          "talent",
        ),
      );
  const filters = `<select data-filter="talent-db" aria-label="Talent database">${option("", "Both databases")}<option value="A" ${database === "A" ? "selected" : ""}>A · With portfolio</option><option value="B" ${database === "B" ? "selected" : ""}>B · Without portfolio</option></select>`;
  return (
    heading(
      "THE PEOPLE BEHIND THE FRAME",
      "Talent, thoughtfully curated.",
      "The right face. The right skills. A fee that fits.",
      button("+ Add talent", "new-talent", "", "primary"),
    ) +
    searchbar("Search talent or skills…", filters) +
    cards
  );
}

async function discovery() {
  const [runs, config] = await Promise.all([
    api("/scrapers/runs"),
    api("/studio/integrations"),
  ]);
  const channels = [
    [
      "maps",
      "Business listings",
      "Permitted public directories across your configured Kolkata locations.",
      "discovery",
    ],
    [
      "magicbricks",
      "MagicBricks owners",
      "Recent public listings with explicit owner evidence.",
      "projects",
    ],
    [
      "acres99",
      "99acres owners",
      "Owner-only property leads, with dates verified from listing evidence.",
      "projects",
    ],
    [
      "radar",
      "Podcast & achievement radar",
      "News search and Claude classification of notable new podcast launches.",
      "script",
    ],
  ];
  const cards = `<div class="cards-grid">${channels.map(([id, name, description, i]) => `<article class="integration-card"><span class="metric-icon">${icon(i)}</span><h3>${name}</h3><p>${description}</p><span class="badge ${id === "radar" && (!config.anthropic.configured || !config.news.configured) ? "amber" : ""}">${id === "radar" && (!config.anthropic.configured || !config.news.configured) ? "API keys needed" : "Configure permitted sources"}</span><div>${button("Schedule a run", "schedule", id, "small")}</div></article>`).join("")}</div>`;
  const history = runs.length
    ? `<div class="table-wrap"><table><thead><tr><th>Channel</th><th>Status</th><th>Ingested</th><th>Rejected</th><th>Started / scheduled</th></tr></thead><tbody>${runs.map((run) => `<tr><td><strong>${e(run.channel)}</strong>${run.error_code ? `<span class="subline">${e(human(run.error_code))}</span>` : ""}</td><td>${badge(run.status)}</td><td>${run.ingested}</td><td>${run.rejected}</td><td>${date(run.scheduled_at || run.created_at, true)}</td></tr>`).join("")}</tbody></table></div>`
    : empty(
        "Discovery is ready when you are.",
        "Configure permitted URLs in the local scraper file, start Redis and an RQ worker, then schedule your first run.",
        "",
        "",
        "discovery",
      );
  return (
    heading(
      "GOOD CONNECTIONS START HERE",
      "A little discovery. A lot of possibility.",
      "Find relevant leads from permitted sources, without the duplicate records.",
      button("↻ Refresh", "refresh"),
    ) +
    `<div class="notice">Public pages only. Robots rules and rate limits are respected. Social, LinkedIn, and Upwork login scraping remain disabled.</div>` +
    cards +
    `<h2 class="section-title">Discovery history</h2>` +
    panel("Scraper runs", history)
  );
}

async function edits() {
  currentProjects = await api("/projects");
  const selected =
    new URLSearchParams(location.hash.split("?")[1] || "").get("project") ||
    currentProjects[0]?.id;
  const history = selected ? await api(`/projects/${selected}/feedback`) : [];
  const body = history.length
    ? history
        .map(
          (review) =>
            `<article class="review-card"><div class="review-header"><div><span class="eyebrow">EDIT NOTES · ${date(review.created_at)}</span><h3>${e(review.text)}</h3></div>${badge(review.status)}</div>${review.operations.length ? review.operations.map((op) => `<div class="script-block"><h4>${e(human(op.operation)).toUpperCase()}${op.scene_id ? " · " + e(op.scene_id) : ""}</h4><p>${op.start_seconds !== null && op.start_seconds !== undefined ? `${op.start_seconds}s → ${op.end_seconds}s<br>` : ""}${e(op.value || op.reason)}</p></div>`).join("") : "<p>No actionable operations extracted. Clarification may be needed.</p>"}${review.status === "pending" ? `<div class="review-actions">${button("Review operations", "review-feedback", review.id, "small")}</div>` : `<p class="hint">Reviewed by ${e(review.reviewed_by)}. Operations remain unapplied.</p>`}</article>`,
        )
        .join("")
    : empty(
        "A fresh pair of eyes.",
        "Paste client feedback or a voice transcript. Review proposed edits before an editor applies them.",
        "new-feedback",
        "Parse feedback",
        "edits",
      );
  return (
    heading(
      "THE EDITOR’S DESK",
      "Notes that move the story forward.",
      "Turn client feedback into clear, reviewable edit instructions.",
      button("+ Parse feedback", "new-feedback", "", "primary"),
    ) +
    `<div class="notice">Feedback is never auto-applied, including after approval. Resolve assembly runs separately on your editing machine.</div><div class="toolbar"><div class="filter-group"><select data-filter="edit-project" aria-label="Select project for feedback">${currentProjects.map((p) => `<option ${p.id === selected ? "selected" : ""} value="${p.id}">${e(p.name)}</option>`).join("") || option("", "Create a project first")}</select></div></div>` +
    panel("Feedback for review", body)
  );
}

async function invoices() {
  const [items, notices, projects] = await Promise.all([
    api("/invoices"),
    api("/invoices/notices"),
    api("/projects"),
  ]);
  const names = Object.fromEntries(projects.map((p) => [p.id, p.name]));
  const body = items.length
    ? `<div class="table-wrap"><table><thead><tr><th>Invoice / client</th><th>Project</th><th>Amount</th><th>Due</th><th>Status</th><th></th></tr></thead><tbody>${items.map((item) => `<tr class="searchable"><td><strong>${e(item.external_id)}</strong><span class="subline">${e(item.client_name)}</span></td><td>${e(names[item.project_id] || "Project")}</td><td>${money(item.amount, item.currency)}</td><td>${date(item.due_date, true)}</td><td>${badge(item.status)}</td><td>${button("Review", "invoice-detail", item.id, "small")}</td></tr>`).join("")}</tbody></table></div>`
    : empty(
        "Keep the business side in frame.",
        "Track non-payment milestones and review suspension notices before anything reaches a client.",
        "new-invoice",
        "Add an invoice",
        "invoices",
      );
  const drafts = notices.length
    ? notices
        .map(
          (notice) =>
            `<article class="review-card"><div class="review-header"><h3>Suspension notice · ${date(notice.created_at)}</h3>${badge(notice.status)}</div><p>${e(notice.content)}</p>${notice.status === "draft" ? button("Review draft", "review-notice", notice.id, "small") : `<p class="hint">Reviewed by ${e(notice.approved_by)} · Not sent by this service.</p>`}</article>`,
        )
        .join("")
    : empty(
        "No suspension drafts.",
        "Day 15 of non-payment pauses the project and creates one draft for human review.",
        "",
        "",
        "invoices",
      );
  return (
    heading(
      "THE BUSINESS OF MAKING",
      "A clear picture of payments.",
      "Thoughtful reminders. Clear milestones. Human decisions.",
      button("+ Add invoice", "new-invoice", "", "primary"),
    ) +
    searchbar("Find an invoice or client…") +
    panel("Invoice register", body) +
    panel("Notices for review", drafts)
  );
}

async function settings() {
  const [config, failures] = await Promise.all([
    api("/studio/integrations"),
    api("/studio/dead-letters"),
  ]);
  const cards = [
    [
      "Claude",
      "Production scripts, fee proposals, and edit feedback.",
      config.anthropic.configured,
      config.anthropic.model,
    ],
    [
      "News search",
      "Podcast and achievement discovery through News API.",
      config.news.configured,
      "NEWS_API_KEY",
    ],
    [
      "Resolve Studio",
      "Local footage and rough assembly on the editing workstation.",
      null,
      "Separate workstation package",
    ],
  ];
  return (
    heading(
      "KEEP THE STUDIO IN SYNC",
      "Workspace settings",
      "Integration status and events that need a closer look.",
      button("↻ Refresh", "refresh"),
    ) +
    `<div class="cards-grid">${cards.map(([title, description, ready, note]) => `<article class="integration-card"><span class="metric-icon">${icon(title === "Resolve Studio" ? "edits" : "settings")}</span><h3>${title}</h3><p>${description}</p><span class="badge ${ready === null ? "blue" : ready ? "green" : "amber"}">${ready === null ? "Workstation required" : ready ? "Configured" : "Needs configuration"}</span><p class="hint">${e(note)}</p></article>`).join("")}</div><h2 class="section-title">Local configuration</h2>` +
    panel(
      "Your environment",
      `<div class="panel-body"><p class="hint">Keep provider keys in the server’s <code>.env</code> file, then restart the API and workers. Keys are never shown or edited in the browser.</p><div class="detail-grid"><div class="detail-stat"><small>SCRAPER CONFIGURATION</small><strong>${e(config.scrapers.config_file)}</strong><p class="hint">${config.scrapers.delay_seconds}s minimum delay · Proxy ${config.scrapers.proxy_configured ? "configured" : "not configured"}</p></div><div class="detail-stat"><small>WORKSPACE AUTHENTICATION</small><strong>Private studio session</strong><p class="hint">HttpOnly, SameSite cookie. n8n uses the API key header.</p></div></div><p class="hint"><a class="button small" href="/docs" target="_blank" rel="noopener">API documentation ↗</a></p></div>`,
    ) +
    panel(
      "Events needing attention",
      failures.length
        ? `<div class="table-wrap"><table><thead><tr><th>Event</th><th>Reason</th><th>Attempts</th><th>Status</th><th></th></tr></thead><tbody>${failures.map((f) => `<tr><td><strong>${e(human(f.job_type))}</strong><span class="subline">${date(f.created_at)} · ${e(f.request_id.slice(0, 8))}</span></td><td>${e(human(f.error_code))}</td><td>${f.attempt_count}</td><td>${badge(f.status)}</td><td>${f.status === "pending" ? button("Mark resolved", "resolve-failure", f.id, "small") : ""}</td></tr>`).join("")}</tbody></table></div>`
        : empty(
            "Everything is in the clear.",
            "Failed provider requests and ambiguous matches will appear here for review.",
            "",
            "",
            "settings",
          ),
      "",
      "Mark resolved after reviewing and correcting the event. Payloads remain in the database.",
    )
  );
}

async function navigate() {
  if ($("#workspace").hidden) return;
  const version = ++pageVersion;
  const route = (location.hash.slice(1) || "overview").split("?")[0];
  const [view, id] = route.split("/");
  const name = nav.find(([key]) => key === view)?.[1] || "Overview";
  $("#breadcrumb").textContent = name;
  document.querySelectorAll("[data-nav]").forEach((node) => {
    node.classList.toggle("active", node.dataset.nav === view);
    node.setAttribute(
      "aria-current",
      node.dataset.nav === view ? "page" : "false",
    );
  });
  $("#sidebar").classList.remove("open");
  content.innerHTML =
    '<div class="loading-state">Bringing the workspace into focus…</div>';
  try {
    const renderers = {
      overview,
      leads,
      projects: () => (id ? projectDetail(id) : projects()),
      talent,
      discovery,
      edits,
      invoices,
      settings,
    };
    const html = await (renderers[view] || overview)();
    if (version !== pageVersion) return;
    content.innerHTML = html;
    document.title = `${name} · Frame Katha Studio`;
  } catch (error) {
    if (version === pageVersion)
      content.innerHTML = heading(
        "WORKSPACE",
        "Couldn’t open this view.",
        e(error.message),
        button("Try again", "refresh"),
      );
  }
}

document.addEventListener("input", (event) => {
  if (event.target.matches("[data-search]")) {
    const value = event.target.value.toLocaleLowerCase();
    content
      .querySelectorAll(".searchable")
      .forEach(
        (node) =>
          (node.hidden = !node.textContent.toLocaleLowerCase().includes(value)),
      );
  }
});
document.addEventListener("change", async (event) => {
  const type = event.target.dataset.filter;
  if (type === "lead-status" || type === "lead-channel") {
    const params = new URLSearchParams();
    const status = $('[data-filter="lead-status"]').value,
      channel = $('[data-filter="lead-channel"]').value;
    if (status) params.set("status", status);
    if (channel) params.set("channel", channel);
    go("leads?" + params);
  } else if (type === "talent-db")
    go(
      "talent" + (event.target.value ? "?database=" + event.target.value : ""),
    );
  else if (type === "edit-project") go("edits?project=" + event.target.value);
});

async function projectOptions() {
  const projects = await api("/projects");
  if (!projects.length) throw new Error("Create a project first.");
  return projects.map((p) => option(p.id, p.name)).join("");
}
async function saveAndRefresh(message) {
  modal.close();
  toast(message);
  await navigate();
}

const actions = {
  refresh: () => navigate(),
  "close-modal": () => modal.close(),
  "edit-project": async (id) => {
    const p = await api("/projects/" + id);
    showModal(
      "Refine the production details.",
      form(
        field("Project name", "name", { value: p.name }) +
          row(
            field("Client / business name", "client_name", {
              value: p.client_name,
            }),
            field("Client email", "client_email", {
              type: "email",
              required: false,
              value: p.client_email || "",
            }),
          ) +
          area("The brief", "requirement") +
          field("Required skills, separated by commas", "required_skills", {
            required: false,
            value: p.required_skills.join(", "),
          }) +
          row(
            field("Minimum fee per talent", "min_fee", {
              type: "number",
              min: 0,
              step: ".01",
              value: p.min_fee,
            }),
            field("Maximum fee per talent", "max_fee", {
              type: "number",
              min: 0,
              step: ".01",
              value: p.max_fee,
            }),
          ) +
          row(
            field("Shoot date", "shoot_date", {
              type: "date",
              required: false,
              value: p.shoot_date || "",
            }),
            field("Call time (IST)", "call_time", {
              type: "time",
              required: false,
              value: p.call_time || "",
            }),
          ) +
          row(
            field("Shoot location", "location", {
              required: false,
              value: p.location || "",
            }),
            field("Cinematographer", "cinematographer", {
              required: false,
              value: p.cinematographer || "",
            }),
          ),
        "Save project",
        "After casting is submitted, client details, fee range, currency, and shoot date are fixed to protect the approval record.",
      ),
      async (data) => {
        await api("/projects/" + id, {
          method: "PUT",
          body: JSON.stringify({
            ...compact(data),
            currency: p.currency,
            required_skills: splitTags(data.required_skills),
          }),
        });
        await saveAndRefresh("Production details updated.");
      },
    );
    $('#modal-body textarea[name="requirement"]').value = p.requirement;
  },
  "edit-talent": async (id) => {
    const t = await api("/talent/" + id);
    showModal(
      "Keep the library current.",
      form(
        field("Full name", "name", { value: t.name }) +
          row(
            field("Email", "email", {
              type: "email",
              required: false,
              value: t.email || "",
            }),
            field("Phone", "phone", {
              type: "tel",
              required: false,
              value: t.phone || "",
            }),
          ) +
          field("Portfolio URL", "portfolio_url", {
            type: "url",
            required: false,
            value: t.portfolio_url || "",
          }) +
          field("Skills, separated by commas", "skills", {
            value: t.skills.join(", "),
          }) +
          row(
            field("Fee rate", "fee_rate", {
              type: "number",
              min: 0,
              step: ".01",
              value: t.fee_rate,
            }),
            field("Followers", "followers", {
              type: "number",
              min: 0,
              value: t.followers,
            }),
          ) +
          field("Unavailable dates, separated by commas", "unavailable_dates", {
            required: false,
            value: t.unavailable_dates.join(", "),
          }) +
          `<label><input type="checkbox" name="available" ${t.available ? "checked" : ""}> Available for projects</label>`,
        "Save changes",
        "Existing client approval records retain their originally proposed fee.",
      ),
      async (data, node) => {
        await api("/talent/" + id, {
          method: "PUT",
          body: JSON.stringify({
            ...compact(data),
            currency: t.currency,
            skills: splitTags(data.skills),
            unavailable_dates: splitTags(data.unavailable_dates),
            available: node.elements.available.checked,
          }),
        });
        await saveAndRefresh("Talent details updated.");
      },
    );
  },
  "new-lead": () =>
    showModal(
      "A new conversation.",
      form(
        field("Business name", "business_name", { maxlength: 300 }) +
          row(
            field("Email", "email", { type: "email", required: false }),
            field("Phone", "phone", { type: "tel", required: false }),
          ) +
          row(
            field("City", "city", { required: false, value: "Kolkata" }),
            field("Locality", "locality", { required: false }),
          ) +
          select(
            "Source",
            "channel",
            ["manual", "maps", "magicbricks", "acres99", "radar"]
              .map((v) => option(v, human(v)))
              .join(""),
          ) +
          field("Website", "website", { type: "url", required: false }) +
          '<label><input type="checkbox" name="opted_out"> This contact has opted out of outreach</label>',
        "Add lead",
        "Existing contacts and matching businesses are merged into one master lead.",
      ),
      async (data, node) => {
        await post("/leads/ingest", {
          ...compact(data),
          opted_out: node.elements.opted_out.checked,
          idempotency_key: crypto.randomUUID(),
        });
        await saveAndRefresh("Lead saved. Duplicates checked.");
      },
    ),
  "new-project": () =>
    showModal(
      "A story starts here.",
      form(
        field("Project name", "name", { maxlength: 300 }) +
          row(
            field("Client / business name", "client_name"),
            field("Client email", "client_email", {
              type: "email",
              required: false,
            }),
          ) +
          area(
            "The brief",
            "requirement",
            "What are we making, and who is it for?",
          ) +
          field("Required skills, separated by commas", "required_skills", {
            required: false,
            placeholder: "Acting, Bengali, dance",
          }) +
          row(
            field("Minimum fee per talent (INR)", "min_fee", {
              type: "number",
              min: 0,
              step: ".01",
              value: 0,
            }),
            field("Maximum fee per talent (INR)", "max_fee", {
              type: "number",
              min: 0,
              step: ".01",
            }),
          ) +
          row(
            field("Shoot date", "shoot_date", {
              type: "date",
              required: false,
            }),
            field("Call time (IST)", "call_time", {
              type: "time",
              required: false,
            }),
          ) +
          row(
            field("Shoot location", "location", { required: false }),
            field("Cinematographer", "cinematographer", { required: false }),
          ),
        "Create project",
        "Shoot details are needed before a call sheet can be generated.",
      ),
      async (data) => {
        await post("/projects", {
          ...compact(data),
          required_skills: splitTags(data.required_skills),
        });
        await saveAndRefresh("Project created. Let’s make something.");
      },
    ),
  "new-talent": () =>
    showModal(
      "Add a collaborator.",
      form(
        field("Full name", "name") +
          row(
            field("Email", "email", { type: "email", required: false }),
            field("Phone", "phone", { type: "tel", required: false }),
          ) +
          field("Portfolio URL", "portfolio_url", {
            type: "url",
            required: false,
          }) +
          field("Skills, separated by commas", "skills", {
            placeholder: "Acting, Bengali, modelling",
          }) +
          row(
            field("Fee rate (INR)", "fee_rate", {
              type: "number",
              min: 0,
              step: ".01",
            }),
            field("Followers", "followers", {
              type: "number",
              min: 0,
              value: 0,
            }),
          ) +
          field("Unavailable dates, separated by commas", "unavailable_dates", {
            required: false,
            placeholder: "YYYY-MM-DD, YYYY-MM-DD",
          }) +
          '<label><input type="checkbox" name="available" checked> Available for projects</label>',
        "Save talent",
        "Provide an email, phone, or portfolio. Adding a portfolio places the record in Database A.",
      ),
      async (data, node) => {
        await post("/talent/import", {
          ...compact(data),
          skills: splitTags(data.skills),
          unavailable_dates: splitTags(data.unavailable_dates),
          available: node.elements.available.checked,
        });
        await saveAndRefresh("Talent library updated.");
      },
    ),
  "view-lead": async (id) => {
    const lead = await api("/leads/" + id);
    showModal(
      lead.business_name,
      `<div class="detail-grid"><div class="detail-stat"><small>CONTACT</small><strong>${e(lead.primary_email || "No email")}</strong><p class="hint">${e(lead.primary_phone || "No phone")}</p></div><div class="detail-stat"><small>LOCATION</small><strong>${e(lead.locality || lead.city || "Not provided")}</strong><p class="hint">${lead.opted_out ? "Opted out — do not contact" : "Check opt-out before every outreach"}</p></div></div><h3 class="section-title">Source references</h3>${lead.sources.map((s) => `<div class="script-block"><h4>${e(s.channel)} · ${s.hit_count} observation${s.hit_count === 1 ? "" : "s"}</h4><p>${s.source_url ? `<a href="${e(s.source_url)}" target="_blank" rel="noopener">Open source ↗</a>` : "Manual entry"} · ${date(s.last_seen_at)}</p></div>`).join("")}<h3 class="section-title">All known contacts</h3><p class="hint">${lead.identities.map((i) => e(i.normalized_value)).join("<br>") || "No contact identities"}</p>` +
        form(
          select(
            "Lead status",
            "status",
            ["new", "qualified", "contacted", "won", "lost", "archived"]
              .map(
                (v) =>
                  `<option ${v === lead.status ? "selected" : ""} value="${v}">${human(v)}</option>`,
              )
              .join(""),
          ),
          "Update status",
        ),
      async (data) => {
        await patch(`/leads/${id}/status`, data);
        await saveAndRefresh("Lead status updated.");
      },
    );
    if (!lead.opted_out)
      $("#modal-body").insertAdjacentHTML(
        "beforeend",
        `<div class="detail-actions">${button("Record an opt-out", "opt-out", id, "danger small")}</div>`,
      );
  },
  "opt-out": (id) =>
    showModal(
      "Respect the request.",
      form(
        area("Opt-out reason", "reason", "Requested unsubscribe", false),
        "Record opt-out",
        "This cannot be cleared through ingestion or the workspace.",
      ),
      async (data) => {
        await patch(`/leads/${id}/opt-out`, data);
        await saveAndRefresh("Opt-out recorded. Do not contact this lead.");
      },
    ),
  "lead-next": () => leadPage(50),
  "lead-prev": () => leadPage(-50),
  "generate-script": async (id) => {
    const pattern = await api(`/projects/${id}/script-pattern`);
    showModal(
      "From brief to first draft.",
      form(
        row(
          field("Dialogue language", "language", { value: pattern.language }),
          field("Runtime in seconds", "duration_seconds", {
            type: "number",
            min: 5,
            max: 600,
            value: pattern.duration_seconds,
          }),
        ) +
          field("Creative tone", "tone", { value: pattern.tone }) +
          area(
            "Optional brief override",
            "requirement",
            "Leave blank to use the project brief.",
            false,
          ),
        "Generate draft",
        "Uses the saved customer pattern. Changes here apply to this draft only. Uses Claude and needs creative review.",
      ),
      async (data) => {
        await post(`/projects/${id}/script`, compact(data));
        await saveAndRefresh("A new script draft is ready for review.");
      },
    );
  },
  "script-pattern": async (id) => {
    const pattern = await api(`/projects/${id}/script-pattern`);
    const labels = {language: "Dialogue language", duration_seconds: "Runtime in seconds",
      tone: "Creative tone", topic: "Topic", content_type: "Content type (ad, reel, testimonial)",
      character_count: "Number of characters", location_description: "Location description"};
    const fields = Object.entries(labels).map(([name, label]) => field(label, name, {
      value: pattern[name] ?? "", required: ["language", "duration_seconds", "tone"].includes(name),
      ...(["duration_seconds", "character_count"].includes(name) ? {type: "number",
        min: name === "duration_seconds" ? 5 : 0, max: name === "duration_seconds" ? 600 : 100} : {})
    })).join("");
    showModal("Customer script pattern", form(fields +
      `<label>Shoot setting<select aria-label="Shoot setting" name="shoot_setting"><option value="">No preference</option>${["indoor", "outdoor", "mixed"].map(v => `<option value="${v}" ${pattern.shoot_setting === v ? "selected" : ""}>${v}</option>`).join("")}</select></label>` +
      [ ["pattern_instructions", "Recurring story structure / pattern"],
        ["customer_challenges", "Customer problems and challenges"],
        ["agreement_notes", "Agreed deliverables and constraints"] ].map(([name, label]) =>
        `<label>${label}<textarea name="${name}">${e(pattern[name] || "")}</textarea></label>`).join(""),
      "Save customer pattern", "Applies to future drafts for all projects with the same client name (ignoring case and extra spaces). Existing script versions stay saved. Clear optional fields to remove a preference."),
      async (data) => {
        await api(`/projects/${id}/script-pattern`, {method: "PUT", body: JSON.stringify(compact(data))});
        await saveAndRefresh("Customer pattern saved for future scripts.");
      });
  },
  "import-script": (id) => showModal("Import a production script", form(
    field("Production script JSON", "script_file", {type: "file"}), "Import script",
    "Choose a structured production-script JSON file, including a downloaded script version. Saves a new version for the Resolve workflow."),
    async (_data, formNode) => {
      const file = formNode.elements.script_file.files[0];
      if (!file || file.size > 1000000) throw new Error("Choose a JSON file smaller than 1 MB.");
      let document;
      try { document = JSON.parse(await file.text()); }
      catch { throw new Error("The file must contain valid JSON."); }
      await post(`/projects/${id}/scripts/import`, document.output || document);
      await saveAndRefresh("Script imported as a new version.");
    }),
  "download-script": async (id) =>
    downloadJSON(await api(`/projects/${id}/script`), "production-script.json"),
  match: async (id) => {
    const data = await post(`/projects/${id}/match`);
    const body = data.matches.length
      ? data.matches
          .map(
            (item) =>
              `<div class="project-row"><div class="project-icon">${e(initials(item.talent.name))}</div><div class="project-info"><strong>${e(item.talent.name)} · ${item.score}% match</strong><small>${e(item.matched_skills.join(", "))} · ${money(item.suggested_fee, item.talent.currency)}</small></div>${button("Select", "select-talent", `${id}|${item.talent.id}|${item.suggested_fee}`, "small")}</div>`,
          )
          .join("")
      : empty(
          "No matching talent yet.",
          "Add talent with the right skills, fee range, currency, and shoot availability.",
          "",
          "",
          "talent",
        );
    showModal("People for this project.", body);
  },
  "select-talent": (value) => {
    const [projectId, talentId, fee] = value.split("|");
    showModal(
      "Propose talent for the cast.",
      form(
        field("Proposed fee", "proposed_fee", {
          type: "number",
          min: 0,
          step: ".01",
          value: fee,
        }),
        "Add to selection",
        "The client must approve this selection before it appears on a call sheet.",
      ),
      async (data) => {
        await post(`/projects/${projectId}/selections`, {
          talent_id: talentId,
          ...data,
        });
        await saveAndRefresh("Talent selected for client review.");
      },
    );
  },
  "send-client": async (id) => {
    const packet = await post(`/projects/${id}/send-to-client`);
    showModal(
      "Client packet prepared.",
      `<div class="notice">${packet.talent.length} selection${packet.talent.length === 1 ? "" : "s"} submitted for review. This service has not sent a message. Use your n8n workflow to deliver the packet.</div><div class="code-block">${e(JSON.stringify(packet, null, 2))}</div><div class="detail-actions">${button("Download packet", "download-packet", id, "primary")}</div>`,
    );
    $('#modal-body [data-action="download-packet"]').addEventListener(
      "click",
      () => downloadJSON(packet, "client-packet.json"),
      { once: true },
    );
    await navigate();
  },
  "client-decision": (value) => {
    const [id, selection] = value.split("|");
    showModal(
      "Record the client’s decision.",
      form(
        select(
          "Decision",
          "decision",
          option("approved", "Approve selection") +
            option("rejected", "Reject selection"),
        ) +
          field("Approved / reviewed by", "approved_by") +
          area(
            "Decision note",
            "note",
            "Record the client’s actual decision.",
            false,
          ),
        "Record decision",
        "Record an actual client decision. This action creates an approval record.",
      ),
      async (data) => {
        await post(`/projects/${id}/client-approval`, {
          ...data,
          selection_id: selection,
        });
        await saveAndRefresh("Client decision recorded.");
      },
    );
  },
  "talent-detail": async (id) => {
    const t = await api("/talent/" + id);
    showModal(
      t.name,
      `<div class="detail-grid"><div class="detail-stat"><small>CONTACT</small><strong>${e(t.email || t.phone || "Portfolio contact")}</strong><p class="hint">${e(t.phone || "")}</p></div><div class="detail-stat"><small>FEE RATE</small><strong>${money(t.fee_rate, t.currency)}</strong><p class="hint">${t.available ? "Available" : "Unavailable"}</p></div></div><h3 class="section-title">Skills & portfolio</h3>${tags(t.skills)}${t.portfolio_url ? `<p><a class="button small" target="_blank" rel="noopener" href="${e(t.portfolio_url)}">Open portfolio ↗</a></p>` : ""}<p class="hint">${t.unavailable_dates.length ? "Unavailable: " + e(t.unavailable_dates.join(", ")) : "No blocked dates recorded."}</p><div class="detail-actions">${button("Edit details", "edit-talent", id)}${button("Draft fee proposal", "negotiate", id, "primary")}</div>`,
    );
  },
  negotiate: async (id) => {
    const options = await projectOptions();
    showModal(
      "A proposal, never a promise.",
      form(
        select("Project", "project_id", options) +
          area(
            "Conversation so far",
            "conversation",
            "Paste the fee discussion for context.",
          ),
        "Draft proposal",
        "Claude proposes an amount within project limits. It never confirms or sends a booking.",
      ),
      async (data) => {
        const result = await post(`/talent/${id}/negotiate`, {
          project_id: data.project_id,
          conversation: [{ role: "user", content: data.conversation }],
        });
        showModal(
          "Fee proposal · human review.",
          `<div class="notice">${money(result.proposed_fee, result.currency)} proposed. No booking or fee confirmed.</div><div class="script-block"><h4>PROPOSED NEXT REPLY</h4><p>${e(result.next_reply)}</p></div><p class="hint">Internal rationale: ${e(result.rationale)}</p>`,
        );
      },
    );
  },
  schedule: (id) =>
    showModal(
      "Set discovery in motion.",
      form(
        `<div class="notice">Channel: ${e(id)}. Requires configured permitted sources, local Redis, and an RQ worker.</div>` +
          field(
            "Run at (local timezone) — leave blank for now",
            "scheduled_at",
            { type: "datetime-local", required: false },
          ),
        "Queue run",
        "Future schedules are converted to timezone-aware timestamps. No login-based scraping is permitted.",
      ),
      async (data) => {
        await post("/scrapers/runs", {
          channel: id,
          ...(data.scheduled_at
            ? { scheduled_at: new Date(data.scheduled_at).toISOString() }
            : {}),
        });
        await saveAndRefresh("Discovery run queued.");
      },
    ),
  "project-feedback": (id) => go("edits?project=" + id),
  "new-feedback": async () => {
    const options = await projectOptions();
    showModal(
      "Make the feedback actionable.",
      form(
        select("Project", "project_id", options) +
          area(
            "Feedback or voice transcript",
            "text",
            "Trim scene-1 from 2 to 5 seconds…",
          ),
        "Parse for review",
        "Voice feedback can be transcribed with the separate Resolve workstation CLI. No edits are applied.",
      ),
      async (data) => {
        const result = await post(`/projects/${data.project_id}/feedback`, {
          text: data.text,
        });
        modal.close();
        go("edits?project=" + data.project_id);
        toast(
          result.clarification_needed.length
            ? result.clarification_needed.join(" ")
            : "Proposed edits saved for human review.",
        );
      },
    );
  },
  "review-feedback": (id) =>
    showModal(
      "Review the proposed operations.",
      form(
        select(
          "Decision",
          "decision",
          option("approved", "Approve for the editor") +
            option("rejected", "Reject operations"),
        ) + field("Reviewed by", "reviewed_by"),
        "Record review",
        "Approving does not apply edits. The editor still makes the changes in Resolve.",
      ),
      async (data) => {
        await post(`/feedback/${id}/review`, data);
        await saveAndRefresh("Review recorded. No edits applied.");
      },
    ),
  "new-invoice": async () => {
    const options = await projectOptions();
    showModal(
      "Bring an invoice into view.",
      form(
        select("Project", "project_id", options) +
          field("Invoice reference", "external_id") +
          row(
            field("Amount (project currency)", "amount", {
              type: "number",
              min: 0,
              step: ".01",
            }),
            field("Due date", "due_date", { type: "date" }),
          ) +
          select(
            "Payment status",
            "status",
            ["unpaid", "paid", "disputed", "cancelled"]
              .map((v) => option(v, human(v)))
              .join(""),
          ),
        "Save & evaluate",
        "Overdue milestones are evaluated in Asia/Kolkata. Day 15 pauses work and creates a draft notice.",
      ),
      async (data) => {
        const result = await post("/invoices/evaluate", data);
        await saveAndRefresh(`Invoice saved · ${human(result.action)}.`);
      },
    );
  },
  "invoice-detail": async (id) => {
    const result = await post(`/invoices/${id}/evaluate`);
    const item = result.invoice;
    showModal(
      item.external_id,
      `<div class="detail-grid"><div class="detail-stat"><small>AMOUNT DUE</small><strong>${money(item.amount, item.currency)}</strong><p class="hint">${e(item.client_name)}</p></div><div class="detail-stat"><small>PAYMENT MILESTONE</small><strong>${result.days_overdue} days overdue</strong><p class="hint">${e(human(result.action))}</p></div></div>${result.work_paused ? '<div class="notice warning" style="margin-top:16px">Work is paused. Payment updates do not automatically resume production.</div>' : ""}` +
        form(
          select(
            "Payment status",
            "status",
            ["unpaid", "paid", "disputed", "cancelled"]
              .map(
                (v) =>
                  `<option ${v === item.status ? "selected" : ""} value="${v}">${human(v)}</option>`,
              )
              .join(""),
          ),
          "Update status",
        ),
      async (data) => {
        await patch(`/invoices/${id}/status`, data);
        await saveAndRefresh("Invoice status updated.");
      },
    );
  },
  "review-notice": (id) =>
    showModal(
      "Review the suspension draft.",
      form(
        select(
          "Decision",
          "decision",
          option("approved", "Approve draft") +
            option("rejected", "Reject draft"),
        ) + field("Reviewed by", "reviewed_by"),
        "Record review",
        "This service never sends the notice. Your n8n workflow must use an approved draft and recheck payment status.",
      ),
      async (data) => {
        await post(`/invoices/notices/${id}/review`, data);
        await saveAndRefresh("Notice reviewed. Nothing sent.");
      },
    ),
  resume: (id) =>
    showModal(
      "Resume production.",
      form(
        field("Reviewed by", "reviewed_by") +
          area("Review note", "note", "Confirm payment has been checked."),
        "Resume project",
        "Resolve unpaid or disputed invoices at day 15+ before resuming.",
      ),
      async (data) => {
        await post(`/projects/${id}/resume`, data);
        await saveAndRefresh("Project work resumed.");
      },
    ),
  "resolve-failure": (id) =>
    showModal(
      "Close this review item.",
      form(
        '<p class="hint">Mark this event resolved after reviewing its database payload and correcting the underlying issue. This does not replay the event.</p>',
        "Mark resolved",
      ),
      async () => {
        await post(`/studio/dead-letters/${id}/resolve`);
        await saveAndRefresh("Event marked resolved.");
      },
    ),
};

function leadPage(delta) {
  const p = new URLSearchParams(location.hash.split("?")[1] || "");
  p.set("offset", Math.max(0, (Number(p.get("offset")) || 0) + delta));
  go("leads?" + p);
}
function downloadJSON(data, filename) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.addEventListener("click", async (event) => {
  const node = event.target.closest("[data-action]");
  if (!node) return;
  const action = actions[node.dataset.action];
  if (!action) return;
  event.preventDefault();
  node.disabled = true;
  try {
    await action(node.dataset.id);
  } catch (error) {
    toast(error.message, true);
  } finally {
    node.disabled = false;
  }
});

try {
  await api("/auth/session");
  showWorkspace();
  await navigate();
} catch {
  showLogin();
}
