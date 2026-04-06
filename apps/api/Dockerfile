FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "sqlmodel>=0.0.22" \
    "sqlalchemy[asyncio]>=2.0.35" \
    "asyncpg>=0.30.0" \
    "alembic>=1.14.0" \
    "pydantic-settings>=2.6.0" \
    "httpx>=0.27.0" \
    "pgvector>=0.3.6" \
    "python-multipart>=0.0.12" \
    "python-dateutil>=2.9.0"

# Copy application code
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
