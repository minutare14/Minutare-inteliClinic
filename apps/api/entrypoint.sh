#!/bin/sh
# entrypoint.sh - API startup sequence for production
# Runs connectivity check -> migrations -> optional seed -> optional webhook -> API server
set -eu

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
    echo "[$(timestamp)] $*"
}

bool_true() {
    case "$(printf '%s' "${1:-false}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

log "======================================================"
log "IntelliClinic API starting"
log "ENV=${APP_ENV:-production}"
log "======================================================"

# Sanitize variables just in case Dokploy env injected CRLF (\r)
export UVICORN_PORT=$(echo "${UVICORN_PORT:-8741}" | tr -d '\r')
export UVICORN_WORKERS=$(echo "${UVICORN_WORKERS:-1}" | tr -d '\r')
export DATABASE_URL=$(echo "${DATABASE_URL:-}" | tr -d '\r')
export BOOTSTRAP_SEED_ON_STARTUP=$(echo "${BOOTSTRAP_SEED_ON_STARTUP:-false}" | tr -d '\r')
export BOOTSTRAP_SEED_WITH_EMBEDDINGS=$(echo "${BOOTSTRAP_SEED_WITH_EMBEDDINGS:-false}" | tr -d '\r')
export BOOTSTRAP_REGISTER_TELEGRAM_WEBHOOK_ON_STARTUP=$(echo "${BOOTSTRAP_REGISTER_TELEGRAM_WEBHOOK_ON_STARTUP:-true}" | tr -d '\r')

startup_started_at=$(date +%s)

log "--> Checking database connectivity"
python - <<'PYEOF'
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        for attempt in range(30):
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                print(f"DB ready (attempt {attempt + 1})")
                return
            except Exception as exc:  # pragma: no cover - startup diagnostics only
                print(f"Waiting for DB... ({attempt + 1}/30): {exc}")
                await asyncio.sleep(2)
        print("ERROR: DB not available after 60s", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()


asyncio.run(check())
PYEOF

migration_started_at=$(date +%s)
log "--> Running database migrations"
# DATABASE_URL is exported above; alembic.ini uses ${DATABASE_URL} variable interpolation
alembic upgrade head
log "--> Migrations complete in $(( $(date +%s) - migration_started_at ))s"

if bool_true "${BOOTSTRAP_SEED_ON_STARTUP}"; then
    seed_started_at=$(date +%s)
    log "--> Seeding initial data"
    if bool_true "${BOOTSTRAP_SEED_WITH_EMBEDDINGS}"; then
        python scripts/seed_data.py --mode db --database-url "${DATABASE_URL}" \
            || log "Seed failed or partially applied (non-fatal, continuing)"
    else
        python scripts/seed_data.py --mode db --skip-embeddings --database-url "${DATABASE_URL}" \
            || log "Seed failed or partially applied (non-fatal, continuing)"
    fi
    log "--> Seed step finished in $(( $(date +%s) - seed_started_at ))s"
else
    log "--> Skipping startup seed (BOOTSTRAP_SEED_ON_STARTUP=false)"
fi

if bool_true "${BOOTSTRAP_REGISTER_TELEGRAM_WEBHOOK_ON_STARTUP}"; then
    webhook_started_at=$(date +%s)
    log "--> Registering Telegram webhook (if configured)"
    python scripts/register_telegram_webhook.py \
        || log "Webhook registration failed (non-fatal)"
    log "--> Webhook bootstrap finished in $(( $(date +%s) - webhook_started_at ))s"
else
    log "--> Skipping Telegram webhook bootstrap"
fi

log "--> Startup bootstrap finished in $(( $(date +%s) - startup_started_at ))s"
log "--> Starting Uvicorn"

LOG_LEVEL_LOWER=$(echo "${APP_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]' | tr -d '\r')

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${UVICORN_PORT}" \
    --workers "${UVICORN_WORKERS}" \
    --log-level "${LOG_LEVEL_LOWER}" \
    --no-access-log
