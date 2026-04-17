# Build context: project root (/)
# docker-compose build context must be set to the repository root
# so that scripts/ directory is accessible during build.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false

# System deps: build tools, libpq (asyncpg), postgresql-client (pg_isready), curl/wget (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps — cached layer, only rebuilds when pyproject.toml changes
COPY apps/api/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.5,<3"
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "sqlmodel>=0.0.22" \
    "sqlalchemy[asyncio]>=2.0.35" \
    "asyncpg>=0.30.0" \
    "alembic>=1.14.0" \
    "pydantic-settings>=2.6.0" \
    "pyyaml>=6.0" \
    "httpx>=0.27.0" \
    "pgvector>=0.3.6" \
    "python-multipart>=0.0.12" \
    "python-dateutil>=2.9.0" \
    "langgraph>=0.2.0" \
    "langchain-core>=0.3.0" \
    "langsmith>=0.3.0" \
    "sentence-transformers>=3.4.0" \
    "PyJWT>=2.8.0" \
    "passlib[bcrypt]>=1.7.4" \
    "bcrypt>=3.2,<4.1" \
    "email-validator>=2.0.0"

# Copy application code
COPY apps/api/app/ ./app/
COPY apps/api/alembic/ ./alembic/
COPY apps/api/alembic.ini ./alembic.ini

# Copy seed and utility scripts (from project root /scripts)
COPY scripts/ ./scripts/

# Copy and prepare startup entrypoint
COPY apps/api/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 8741

HEALTHCHECK --interval=15s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -sf --max-time 8 http://127.0.0.1:8741/health/live || exit 1

ENTRYPOINT ["./entrypoint.sh"]
