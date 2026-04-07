"""API layer — FastAPI application, routes, and schemas.

The API is the delivery mechanism for the InteliClinic product.
Business logic lives in core/. The API layer only:
    - Receives HTTP requests
    - Validates input (Pydantic schemas)
    - Delegates to core services
    - Returns structured responses

Current implementation: apps/api/app/ (backwards compatible)
Migration target: src/inteliclinic/api/

Entry point: src/inteliclinic/api/main.py (to be created in Phase 2 migration)
"""
