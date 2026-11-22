# VPS deployment (Docker Compose + GitHub Actions)

Flow: push to `main` → **CI** (ruff, migrations, pytest on Postgres) → **Deploy** builds the
image, pushes it to GHCR, SSHes to the VPS, runs `alembic upgrade head`, restarts the stack and
smoke-tests `https://DOMAIN/health`. Caddy gets the HTTPS certificate automatically.

Stack (`deploy/docker-compose.yml`): `caddy` (80/443 only) → `web` (FastAPI) → `db` (Postgres 16) +
`redis`, plus an RQ `worker`. Postgres and Redis are not exposed publicly.

## One-time VPS setup (Ubuntu 22.04/24.04)

1. Point a DNS **A record** (e.g. `api.yourdomain.com`) at the VPS IP.
2. Create a deploy user and install Docker:
   ```sh
   adduser --disabled-password deploy && usermod -aG docker deploy   # after Docker is installed
   curl -fsSL https://get.docker.com | sh
   ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
   mkdir -p /opt/framekatha && chown deploy:deploy /opt/framekatha
   ```
3. Generate a dedicated deploy key **on your PC**, add the public key to
   `/home/deploy/.ssh/authorized_keys` on the VPS:
   ```sh
   ssh-keygen -t ed25519 -f framekatha_deploy -N ""
   ```
4. Create `/opt/framekatha/.env` from `deploy/production.env.example` (strong `POSTGRES_PASSWORD`,
   a new `API_KEY`, `DOMAIN`, `ANTHROPIC_API_KEY`). Permissions: `chmod 600`.

## GitHub repository secrets

Settings → Secrets and variables → Actions:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS IP or hostname |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | contents of the private key `framekatha_deploy` |
| `VPS_PORT` | optional, default 22 |
| `DOMAIN` | e.g. `api.yourdomain.com` (used by the smoke test) |

Also: Settings → Actions → General → Workflow permissions → allow **read and write** so the
workflow can push to GHCR.

## Operations

- Logs: `cd /opt/framekatha && docker compose logs -f web`
- Rollback: set `IMAGE=ghcr.io/<owner>/<repo>:<older-sha>` in `.env`, then
  `docker compose up -d`. Migrations are not rolled back automatically.
- Manual deploy: Actions → Deploy → Run workflow.
- **Backups (not automated):** `docker compose exec db pg_dump -U framekatha framekatha | gzip > backup.sql.gz`
  on a cron, copied off the VPS.
- Scrapers need Chromium, which is excluded from the default image. Build with
  `--build-arg WITH_BROWSER=1` if you run them in production.
- The dashboard and API share one API key; keep the domain behind HTTPS only (Caddy does this).
