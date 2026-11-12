# Frame Katha Resolve workstation

This independent package runs **on the editing machine**, using local files (including
a Drive-synced folder). It does not upload raw footage or connect to Drive directly.

```sh
python3.11 -m venv .resolve-venv
source .resolve-venv/bin/activate
pip install -e './resolve[transcription]'
framekatha-resolve --help
```

Install DaVinci Resolve **Studio**, open a project, enable local external scripting,
and set `RESOLVE_SCRIPT_API_MODULES` to the installed
`Developer/Scripting/Modules` directory. Set `RESOLVE_SCRIPT_LIB` if required by your
installation; follow the SDK's installed README for your platform. Whisper runs
locally via faster-whisper and downloads the selected model on first use. Review
your machine's available disk/memory before the first transcription.

Download a project's generated script JSON from the dashboard (or the authenticated
`GET /projects/{id}/script` endpoint) and save it as `script.json`.

```sh
framekatha-resolve watch /path/to/raw --output /path/to/work --script script.json
framekatha-resolve plan --script script.json --transcripts /path/to/work --output plan.json
framekatha-resolve assemble plan.json --name 'Launch rough assembly' --fps 24 \
  --bgm /path/to/licensed-music.wav --lut /path/to/look.cube \
  --render-directory /path/to/renders --render-preset 'Your preset'
```

`ingest` performs one scan; `watch` scans every ten seconds. Recently modified files
are skipped until stable. A local SQLite ledger prevents repeated transcription;
replaced files are reprocessed. Each failed version receives at most three attempts,
then appears with `status='dead_letter'` in `work/ingest.sqlite3`. Error codes are
stored without exception text. Correct the file or reset its attempts/status in the
local ledger to retry. Do not run two watcher processes against the same output.

The planner matches full dialogue lines across up to eight consecutive transcript
segments (with gaps up to 1.5 seconds) and orders them by the script. It preserves
the full dialogue instead of cutting it to the planned duration, reports pacing
warnings, and prevents overlapping source ranges from being reused. Unmatched and
visual-only shots remain listed for manual selection. Inspect
`plan.json` before assembly. `assemble` creates a **new** timeline, applies an optional
LUT on node 1 and/or a `.drx` colour preset, adds the chosen licensed music track on
audio track 2, and optionally queues a render. It **never starts rendering**. Match
the timeline FPS to the intended project format; source FPS is read per media item.
Use a BGM file long enough for the assembly. Music mixing/ducking/fades remain manual.

This produces a **rough assembly cut for a human editor, not a final edit**. It cannot
reliably choose performances, compose B-roll, infer visual-only shots, reconcile
multicam/timecode, mix sound, or deliver final colour. Mixed frame rates, missing
codecs, disabled scripting, unsupported LUT nodes, and differing Resolve SDK versions
can fail explicitly. SDK behavior is tested with a fake adapter; real Studio execution
must be checked on your workstation. Failed assembly may leave a partial new timeline;
inspect/remove it manually before retrying.

Voice feedback can be transcribed independently:

```sh
framekatha-resolve transcribe /path/to/feedback.wav --output feedback.transcript.json
```

To submit its text to the backend parser, set `API_KEY` in the workstation's environment
and add `--feedback-project PROJECT_UUID --api-url http://127.0.0.1:8000` (use HTTPS for
a remote deployment). Feedback parsing creates proposed operations for human review.
No feedback operations are executed by this package, including approved feedback.
