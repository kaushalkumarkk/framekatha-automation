import json
import sqlite3
import time
from pathlib import Path

from resolve.transcribe import transcribe

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mxf", ".mkv", ".wav", ".mp3", ".m4a"}


class FolderIngestor:
    """Durable local ledger. Failed files stop retrying after three attempts."""

    def __init__(self, folder: Path, output: Path, stable_seconds=5, transcriber=transcribe):
        self.folder, self.output = folder.resolve(), output.resolve()
        if not self.folder.is_dir():
            raise ValueError("Watch folder does not exist")
        self.output.mkdir(parents=True, exist_ok=True)
        self.transcriber, self.stable_seconds = transcriber, stable_seconds
        self.ledger = sqlite3.connect(self.output / "ingest.sqlite3")
        self.ledger.execute("""CREATE TABLE IF NOT EXISTS media (
            path TEXT PRIMARY KEY, signature TEXT NOT NULL, attempts INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending', error_code TEXT, transcript_path TEXT)""")

    def scan(self) -> list[dict]:
        results = []
        for path in sorted(self.folder.rglob("*")):
            if (
                path.is_symlink()
                or not path.is_file()
                or path.suffix.lower() not in MEDIA_EXTENSIONS
            ):
                continue
            # Drive-sync files must stop changing before transcription starts.
            stat = path.stat()
            if time.time() - stat.st_mtime < self.stable_seconds:
                continue
            signature = f"{stat.st_size}:{stat.st_mtime_ns}"
            record = self.ledger.execute(
                "SELECT signature, attempts, status FROM media WHERE path=?",
                (str(path),),
            ).fetchone()
            if record and record[0] == signature and (record[2] == "done" or record[1] >= 3):
                continue
            attempts = record[1] if record and record[0] == signature else 0
            self.ledger.execute(
                "INSERT OR REPLACE INTO media VALUES (?, ?, ?, 'running', NULL, NULL)",
                (str(path), signature, attempts + 1),
            )
            self.ledger.commit()
            try:
                transcript = self.transcriber(path)
                after = path.stat()
                if f"{after.st_size}:{after.st_mtime_ns}" != signature:
                    raise RuntimeError("Media changed during transcription")
                import hashlib

                filename = hashlib.sha256(str(path).encode()).hexdigest() + ".transcript.json"
                target = self.output / filename
                temporary = target.with_suffix(".tmp")
                temporary.write_text(json.dumps(transcript, ensure_ascii=False, indent=2))
                temporary.replace(target)
                self.ledger.execute(
                    "UPDATE media SET status='done', transcript_path=? WHERE path=?",
                    (str(target), str(path)),
                )
                results.append(transcript)
            except Exception as error:
                self.ledger.execute(
                    "UPDATE media SET status=?, error_code=? WHERE path=?",
                    (
                        "dead_letter" if attempts + 1 >= 3 else "pending",
                        type(error).__name__,
                        str(path),
                    ),
                )
            self.ledger.commit()
        return results

    def transcripts(self):
        paths = self.ledger.execute("SELECT transcript_path FROM media WHERE status='done'")
        return [json.loads(Path(row[0]).read_text()) for row in paths]

    def close(self):
        self.ledger.close()
