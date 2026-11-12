# Customer script patterns and supplied scripts

Open a project and use **Production script → Customer pattern**. Save the topic,
content type, character count, indoor/outdoor/mixed shoot setting, location description,
language, runtime, tone, recurring story structure, customer challenges and agreement
notes. Optional fields can be cleared. Saving replaces the entire pattern.

Patterns belong to a client name, ignoring case and repeated whitespace, and apply
to all projects with that name. Use distinct client names for distinct businesses.
Renaming a project's client switches it to that client's pattern; it does not rename
the previous client's pattern. Pattern updates affect future generations; old script
versions retain their exact brief and output. Production constraints guide the AI;
check the generated draft before shooting.

**Generate script / New version** loads the saved language, runtime and tone. Changes
in that dialog apply to that draft only. The API also accepts any pattern field as
a one-time override; an explicit `null` clears an optional preference for that draft.

Authenticated endpoints:

* `GET /projects/{id}/script-pattern` returns the client's pattern, or defaults.
* `PUT /projects/{id}/script-pattern` replaces the client's pattern.
* `POST /projects/{id}/script` generates a version with the effective pattern.
* `POST /projects/{id}/scripts/import` saves a validated `ScriptDocument` as a new
  version without calling an AI provider. It accepts the document itself, not the
  version envelope. Import versions are marked `import.v1`.

Use **Import script** to upload a structured JSON production document (up to 1 MB
in the dashboard). A downloaded Framekatha script JSON is also accepted by the
dashboard. The document needs title, shooting_script, screenplay, editing_direction
and bgm_suggestions, matching the schemas in `/docs`. Plain text, PDF and Word files
are not supported by this importer. Invalid scripts do not create versions.

Download the latest script JSON and use the existing [Resolve workflow](../resolve/README.md).
The planner matches dialogue across up to eight consecutive transcript segments,
with gaps no longer than 1.5 seconds. It compares the full line, preserves its full
spoken range, prevents reused overlapping media ranges, and reports pacing warnings
when dialogue exceeds the scripted duration. Visual-only shots and unmatched dialogue
still require manual selection. This is transcript-based rough assembly; visual scene
understanding, performance selection and autonomous final editing are not implemented.

The supplied discussion also describes Udyog AI accounting, social publishing and
a business research assistant. Those belong to the separate Udyog AI product and
are outside this studio automation change.
