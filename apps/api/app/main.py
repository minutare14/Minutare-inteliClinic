from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging

# Import all models so SQLModel metadata is populated
import app.models.patient  # noqa: F401
import app.models.professional  # noqa: F401
import app.models.schedule  # noqa: F401
import app.models.conversation  # noqa: F401
import app.models.audit  # noqa: F401
import app.models.rag  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Minutare Med API starting (env=%s)", settings.app_env)
    
    # ── Logs explícitos de Startup ──
    provider = settings.llm_provider or "auto-detect"
    logger.info("Clínica: %s (id=%s)", settings.clinic_name, settings.clinic_id)
    logger.info("Chatbot name: %s", settings.clinic_chatbot_name or "Assistente")
    logger.info("AI Provider configurado: %s", provider)
    logger.info("Telegram Webhook URL configurado: %s", settings.telegram_webhook_computed_url or "nenhum")
    
    if settings.database_url.startswith("sqlite"):
        from app.core.db import init_db
        await init_db()
        logger.info("SQLite tables created (dev mode)")
        
    logger.info("API Startup completo. Aguardando conexões.")
    yield
    logger.info("Minutare Med API shutting down")


app = FastAPI(
    title="Minutare Med",
    description="Plataforma operacional para clínica médica com IA nativa",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register routes ---
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.patients import router as patients_router  # noqa: E402
from app.api.routes.schedules import router as schedules_router  # noqa: E402
from app.api.routes.conversations import router as conversations_router  # noqa: E402
from app.api.routes.telegram import router as telegram_router  # noqa: E402
from app.api.routes.rag import router as rag_router  # noqa: E402
from app.api.routes.handoff import router as handoff_router  # noqa: E402
from app.api.routes.audit import router as audit_router  # noqa: E402
from app.api.routes.dashboard import router as dashboard_router  # noqa: E402
from app.api.routes.professionals import router as professionals_router  # noqa: E402

API_PREFIX = "/api/v1"

app.include_router(health_router)
app.include_router(patients_router, prefix=API_PREFIX)
app.include_router(schedules_router, prefix=API_PREFIX)
app.include_router(conversations_router, prefix=API_PREFIX)
app.include_router(telegram_router, prefix=API_PREFIX)
app.include_router(rag_router, prefix=API_PREFIX)
app.include_router(handoff_router, prefix=API_PREFIX)
app.include_router(audit_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(professionals_router, prefix=API_PREFIX)
