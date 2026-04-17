from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised in runtime, not unit tests
    from langsmith.run_helpers import trace
except Exception:  # pragma: no cover - graceful fallback if package missing
    trace = None


def configure_langsmith() -> None:
    """Configure LangSmith through environment variables once at startup."""
    os.environ["LANGSMITH_TRACING"] = "true" if settings.langsmith_enabled else "false"

    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id

    logger.info(
        "[TRACE] langsmith_enabled=%s project=%s endpoint=%s",
        str(settings.langsmith_enabled).lower(),
        settings.langsmith_project,
        settings.langsmith_endpoint,
    )


@asynccontextmanager
async def trace_step(
    name: str,
    *,
    run_type: str = "chain",
    inputs: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
):
    """
    Create a LangSmith child run when tracing is available.

    Callers may update ``run.metadata`` and must call ``run.end(outputs=...)`` when
    they want structured outputs to show up in LangSmith. When tracing is disabled,
    this yields ``None`` and the caller continues normally.
    """
    if trace is None:
        yield None
        return

    try:  # pragma: no cover - runtime integration
        async with trace(
            name,
            run_type=run_type,
            inputs=inputs or {},
            tags=tags,
            metadata=metadata,
            project_name=settings.langsmith_project,
        ) as run:
            yield run
    except Exception:
        logger.exception("[TRACE] Failed to create LangSmith step '%s'", name)
        yield None
