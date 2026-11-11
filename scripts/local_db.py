"""Run a project-local PostgreSQL server without Docker or a system installation.

Install the optional runtime: uv pip install -e '.[dev,local]'
Keep this process running; Ctrl-C stops PostgreSQL without removing its data.
"""

import secrets
import signal
from pathlib import Path

import pgserver
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".local" / "postgres"


def main():
    DATA.parent.mkdir(exist_ok=True)
    with pgserver.get_server(DATA, cleanup_mode="stop") as server:
        with psycopg.connect(server.get_uri(), autocommit=True) as conn:
            for name in ("framekatha", "framekatha_test"):
                exists = conn.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
                ).fetchone()
                if not exists:
                    conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        env_path = ROOT / ".env"
        if not env_path.exists():
            # pgserver uses an owner-local Unix socket, with TCP listening disabled.
            db_url = server.get_uri(database="framekatha").replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
            test_url = server.get_uri(database="framekatha_test").replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
            with env_path.open("x", encoding="utf-8") as file:
                file.write(
                    f"DATABASE_URL={db_url}\nTEST_DATABASE_URL={test_url}\n"
                    f"API_KEY={secrets.token_urlsafe(32)}\n"
                    "REDIS_URL=redis://localhost:6379/0\n"
                )
            env_path.chmod(0o600)
            print("Created .env with local database URLs and a generated API key.", flush=True)
        else:
            print(
                "Existing .env preserved; ensure its database URL targets this server.", flush=True
            )
        print(
            "Local PostgreSQL is ready. Ctrl-C stops it; data stays in .local/postgres.", flush=True
        )

        def stop(*_):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, stop)
        try:
            while True:
                signal.pause()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
