#!/bin/sh
# entrypoint.sh — API startup sequence for production
# Runs migrations → seed → API server
set -e

echo "======================================================"
echo "  Minutare InteliClinic — API Starting"
echo "  ENV: ${APP_ENV:-production}"
echo "======================================================"

# Wait for DB (extra safety beyond healthcheck)
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

# Run Alembic migrations
echo "--> Running database migrations..."
alembic upgrade head
echo "    Migrations complete."

# Seed initial data (idempotent — safe to run every start)
echo "--> Seeding initial data..."
python scripts/seed_data.py \
    --mode db \
    --database-url "${DATABASE_URL}" \
    || echo "    Seed skipped or partially applied (non-fatal)."

# Registrar webhook do Telegram automaticamente (idempotente)
# Só executa se TELEGRAM_AUTO_WEBHOOK=true + token e URL definidos
echo "--> Registrando webhook do Telegram (se habilitado)..."
python scripts/register_telegram_webhook.py \
    || echo "    Webhook Telegram: aviso ou skip (não fatal)."

echo "--> Starting Uvicorn..."
echo "    Workers: ${UVICORN_WORKERS:-1}"
echo "    Log level: ${APP_LOG_LEVEL:-info}"
echo "======================================================"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${UVICORN_PORT:-8741}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${APP_LOG_LEVEL:-info}" \
    --no-access-log
