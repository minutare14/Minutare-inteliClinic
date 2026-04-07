"""Observability — structured logging, tracing, and metrics.

Provides a consistent observability stack for all InteliClinic deploys.

Components:
    logging:  Structured JSON logging with correlation IDs
    tracing:  OpenTelemetry trace propagation (future)
    metrics:  Prometheus metrics endpoint (future)

Usage:
    from inteliclinic.core.observability import get_logger

    logger = get_logger(__name__)
    logger.info("Patient message received", extra={"conversation_id": cid})
"""
from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger
