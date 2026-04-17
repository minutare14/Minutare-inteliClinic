from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.observability.langsmith import configure_langsmith

# Import all models so SQLModel metadata is populated
import app.models.patient  # noqa: F401
import app.models.professional  # noqa: F401
import app.models.schedule  # noqa: F401
import app.models.conversation  # noqa: F401
import app.models.audit  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.admin  # noqa: F401
import app.models.auth  # noqa: F401
import app.models.jobs  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    configure_langsmith()
    logger.info("IntelliClinic API starting (env=%s)", settings.app_env)

    provider = settings.llm_provider or "auto-detect"
    logger.info(
        "Clinic ID: %s | AI Provider: %s | Reranker: %s",
        settings.clinic_id, provider,
        f"enabled model={settings.rag_reranker_model}" if settings.rag_reranker_enabled else "disabled",
    )
    logger.info("Telegram Webhook: %s", settings.telegram_webhook_computed_url or "nenhum")

    if settings.database_url.startswith("sqlite"):
        from app.core.db import init_db
        await init_db()
        logger.info("SQLite tables created (dev mode)")

    # ── Seed ClinicSettings (get_or_create) ───────────────────────────────────
    try:
        from app.core.db import async_session_factory
        from app.services.admin_service import AdminService
        async with async_session_factory() as session:
            admin_svc = AdminService(session)
            clinic_cfg = await admin_svc.get_clinic_settings()
            logger.info(
                "[STARTUP] ClinicSettings OK — clinic='%s' bot='%s'",
                clinic_cfg.name or settings.clinic_name or "(vazio)",
                clinic_cfg.chatbot_name or settings.clinic_chatbot_name or "(vazio)",
            )
    except Exception:
        logger.exception("[STARTUP] Falha ao seed ClinicSettings — continuando")

    # ── Seed default admin user (once, on first deploy) ───────────────────────
    try:
        from app.core.db import async_session_factory
        from app.core.auth import seed_default_admin
        async with async_session_factory() as session:
            await seed_default_admin(session)
    except Exception:
        logger.exception("[STARTUP] Falha ao seed admin user — continuando")

    # ── Background workers ────────────────────────────────────────────────────
    from app.workers.followup_worker import run_followup_worker
    worker_task = asyncio.create_task(run_followup_worker(), name="followup_worker")

    logger.info("API Startup completo. Aguardando conexões.")
    yield

    # Graceful shutdown — cancel the background worker
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("IntelliClinic API shutting down")


# Title comes from clinic config, not hardcoded.
# The actual clinic name shown in Swagger UI is resolved at startup.
app = FastAPI(
    title="IntelliClinic — Plataforma Operacional Clínica",
    description=(
        "Sistema operacional clínico híbrido com IA nativa. "
        "1 deploy por clínica. Configurado via Admin ou variáveis de ambiente."
    ),
    version="0.3.0",
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

# ── Register routes ────────────────────────────────────────────────────────────
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.patients import router as patients_router  # noqa: E402
from app.api.routes.schedules import router as schedules_router  # noqa: E402
from app.api.routes.conversations import router as conversations_router  # noqa: E402
from app.api.routes.telegram import router as telegram_router  # noqa: E402
from app.api.routes.rag import router as rag_router  # noqa: E402
from app.api.routes.handoff import router as handoff_router  # noqa: E402
from app.api.routes.audit import router as audit_router  # noqa: E402
from app.api.routes.dashboard import router as dashboard_router  # noqa: E402
from app.api.routes.professionals import router as professionals_router  # noqa: E402
from app.api.routes.admin import router as admin_router  # noqa: E402
from app.api.routes.crm import router as crm_router  # noqa: E402
from app.api.routes.google import router as google_router  # noqa: E402

API_PREFIX = "/api/v1"

app.include_router(health_router)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(patients_router, prefix=API_PREFIX)
app.include_router(schedules_router, prefix=API_PREFIX)
app.include_router(conversations_router, prefix=API_PREFIX)
app.include_router(telegram_router, prefix=API_PREFIX)
app.include_router(rag_router, prefix=API_PREFIX)
app.include_router(handoff_router, prefix=API_PREFIX)
app.include_router(audit_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(professionals_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(crm_router, prefix=API_PREFIX)
app.include_router(google_router, prefix=API_PREFIX)
