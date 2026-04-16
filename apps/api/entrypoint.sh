#!/bin/sh
# entrypoint.sh — API startup sequence for production
# Runs migrations → seed → API server
set -e
set -x  # Habilita modo verbose para logs extremos no Dokploy

echo "======================================================"
echo "  IntelliClinic — API Starting"
echo "  ENV: ${APP_ENV:-production}"
echo "======================================================"

# Sanitize variables just in case Dokploy env injected CRLF (\r)
export UVICORN_PORT=$(echo "${UVICORN_PORT:-8741}" | tr -d '\r')
export UVICORN_WORKERS=$(echo "${UVICORN_WORKERS:-1}" | tr -d '\r')
export DATABASE_URL=$(echo "${DATABASE_URL}" | tr -d '\r')

echo "--> Checking database connectivity..."
python - <<'PYEOF'
import asyncio, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    engine = create_async_engine(url, pool_pre_ping=True)
    for attempt in range(30):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            print(f"    DB ready (attempt {attempt + 1})")
            return
        except Exception as e:
            print(f"    Waiting for DB... ({attempt + 1}/30): {e}")
            await asyncio.sleep(2)
    print("ERROR: DB not available after 60s", file=sys.stderr)
    await engine.dispose()
    sys.exit(1)

asyncio.run(check())
PYEOF

echo "--> Running database migrations..."
alembic upgrade head || { echo "CRITICAL ERROR: Alembic failed"; exit 1; }
echo "    Migrations complete."

echo "--> Seeding initial data..."
python scripts/seed_data.py \
    --mode db \
    --database-url "${DATABASE_URL}" \
    || echo "    Seed failed or partially applied (non-fatal, continuing)."

echo "--> Registrando webhook do Telegram (se habilitado)..."
python scripts/register_telegram_webhook.py || echo "    Webhook falhou (não-fatal)."

echo "--> Starting Uvicorn..."
# Garantir log level exato para evitar Invalid choice do framework
LOG_LEVEL_LOWER=$(echo "${APP_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]' | tr -d '\r')

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${UVICORN_PORT}" \
    --workers "${UVICORN_WORKERS}" \
    --log-level "${LOG_LEVEL_LOWER}" \
    --no-access-log

