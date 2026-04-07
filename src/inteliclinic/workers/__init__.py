"""Background workers — async tasks running outside the request cycle.

Workers handle:
    - Document ingestion (triggered after upload)
    - RAG re-indexing (on schedule or on demand)
    - Anomaly detection batch runs (nightly)
    - Notification dispatch (post-appointment reminders)
    - Audit log archiving

Workers are decoupled from the API and can run as:
    - Celery tasks (recommended for production)
    - APScheduler jobs (for lightweight deploys)
    - Standalone scripts (for one-off runs)

No n8n or external orchestration platforms.
All worker logic is pure Python, deployable on the same VPS as the API.
"""
