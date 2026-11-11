import argparse
import json
import os
import time
from pathlib import Path

from resolve.adapter import assemble
from resolve.ingest import FolderIngestor
from resolve.plan import build_plan
from resolve.transcribe import transcribe


def main():
    parser = argparse.ArgumentParser(description="Frame Katha editing workstation")
    commands = parser.add_subparsers(dest="command", required=True)
    voice = commands.add_parser("transcribe")
    voice.add_argument("file", type=Path)
    voice.add_argument("--output", type=Path, required=True)
    voice.add_argument("--feedback-project")
    voice.add_argument("--api-url", default="http://127.0.0.1:8000")
    for name in ("ingest", "watch"):
        ingest = commands.add_parser(name)
        ingest.add_argument("folder", type=Path)
        ingest.add_argument("--output", type=Path, required=True)
        ingest.add_argument("--script", type=Path)
        ingest.add_argument("--interval", type=int, default=10)
    plan = commands.add_parser("plan")
    plan.add_argument("--script", type=Path, required=True)
    plan.add_argument("--transcripts", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    edit = commands.add_parser("assemble")
    edit.add_argument("plan", type=Path)
    edit.add_argument("--name", required=True)
    edit.add_argument("--fps", type=float, default=24)
    edit.add_argument("--lut")
    edit.add_argument("--colour-preset")
    edit.add_argument("--bgm")
    edit.add_argument("--render-directory")
    edit.add_argument("--render-preset")
    args = parser.parse_args()
    if args.command == "transcribe":
        result = transcribe(args.file)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if args.feedback_project:
            import httpx

            key = os.environ.get("API_KEY")
            if not key:
                raise RuntimeError("API_KEY must be set in the workstation environment")
            response = httpx.post(
                args.api_url.rstrip("/") + f"/projects/{args.feedback_project}/feedback",
                headers={"X-API-Key": key},
                json={"text": " ".join(segment["text"] for segment in result["segments"])},
                timeout=120,
            )
            response.raise_for_status()
            print(json.dumps(response.json()))
    elif args.command in {"ingest", "watch"}:
        if args.interval < 1:
            parser.error("--interval must be positive")
        worker = FolderIngestor(args.folder, args.output)
        try:
            while True:
                worker.scan()
                if args.script:
                    plan = build_plan(json.loads(args.script.read_text()), worker.transcripts())
                    (args.output / "rough-cut.plan.json").write_text(json.dumps(plan, indent=2))
                if args.command == "ingest":
                    break
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
        finally:
            worker.close()
    elif args.command == "plan":
        transcripts = [
            json.loads(path.read_text()) for path in args.transcripts.glob("*.transcript.json")
        ]
        result = build_plan(json.loads(args.script.read_text()), transcripts)
        args.output.write_text(json.dumps(result, indent=2))
    elif args.command == "assemble":
        print(
            json.dumps(
                assemble(
                    json.loads(args.plan.read_text()),
                    args.name,
                    args.fps,
                    args.lut,
                    args.colour_preset,
                    args.bgm,
                    args.render_directory,
                    args.render_preset,
                )
            )
        )


if __name__ == "__main__":
    main()
