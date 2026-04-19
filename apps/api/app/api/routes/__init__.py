from __future__ import annotations

from app.api.routes.document_upload import router as document_upload_router
from app.api.routes.extractions import router as extractions_router

__all__ = ["document_upload_router", "extractions_router"]