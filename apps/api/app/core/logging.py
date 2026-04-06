from __future__ import annotations

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    log_level = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(handler)

    # Silence noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.is_dev else logging.WARNING
    )
