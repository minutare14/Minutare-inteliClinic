"""Pinecone Structured Sync — keeps service/pricing data fresh in the vector index.

When a structured record changes in the DB, this module re-upserts the
updated text to Pinecone so the vector index never serves stale data.
If Pinecone is unavailable, the DB change is preserved — the AI falls
back to live structured data without any drift.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.core.config import settings
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


async def sync_service_to_pinecone(
    service_id: uuid.UUID,
    session: "AsyncSession",
    action: str = "upsert",
) -> bool:
    """
    Re-upsert a service's structured text to Pinecone.

    action: "upsert" | "delete"
    """
    from app.core.pinecone_client import PineconeClient
    from app.repositories.service_repository import ServiceRepository
    from app.services.rag_service import get_embedding

    repo = ServiceRepository(session)
    audit = AuditService(session)

    if action == "delete":
        try:
            pinecone = PineconeClient()
            if pinecone.is_available():
                namespace = settings.clinic_id
                await pinecone.delete_chunks([str(service_id)])
                logger.info(
                    "[PINE_SYNC] service_id=%s action=delete status=success namespace=%s",
                    service_id, namespace,
                )
                await audit.log_event(
                    actor_type="system",
                    actor_id="pinecone_structured_sync",
                    action="pinecone_sync.delete",
                    resource_type="service",
                    resource_id=str(service_id),
                    payload={"action": "delete", "namespace": namespace},
                )
                return True
        except Exception as exc:
            logger.error("[PINE_SYNC] service_id=%s action=delete status=failed error=%s", service_id, exc)
            await audit.log_event(
                actor_type="system",
                actor_id="pinecone_structured_sync",
                action="pinecone_sync.failed",
                resource_type="service",
                resource_id=str(service_id),
                payload={"action": "delete", "error": str(exc)},
            )
            return False
        return True

    # ── Build structured text for upsert ──────────────────────────────────
    svc_dict = await repo.get_service_with_doctors(service_id)
    if not svc_dict:
        logger.warning("[PINE_SYNC] service_id=%s not found — skipping", service_id)
        return False

    svc = svc_dict
    lines = [
        f"Serviço: {svc['name']}",
    ]
    if svc.get("description"):
        lines.append(f"Descrição: {svc['description']}")
    if svc.get("ai_summary"):
        lines.append(f"Resumo: {svc['ai_summary']}")

    base_price = svc.get("base_price")
    if base_price is not None:
        lines.append(f"Valor base: R$ {base_price:,.2f}")

    if svc.get("prices"):
        for p in svc["prices"]:
            ins = p.get("insurance_plan_id") or "particular"
            lines.append(f"Preço ({ins}): R$ {p['price']:,.2f}")

    if svc.get("doctors"):
        names = [d["full_name"] for d in svc["doctors"]]
        lines.append(f"Médicos: {', '.join(names)}")

    if svc.get("rules"):
        for r in svc["rules"]:
            lines.append(f"Regra ({r['rule_type']}): {r['rule_text']}")

    text = "\n".join(lines)

    # ── Generate embedding ────────────────────────────────────────────────────
    try:
        embedding_config = {"provider": settings.embedding_provider, "model": settings.embedding_model}
        embedding = await get_embedding(text, phase="service_sync", embedding_config=embedding_config)
    except Exception as exc:
        logger.error("[PINE_SYNC] service_id=%s embedding failed error=%s", service_id, exc)
        await audit.log_event(
            actor_type="system",
            actor_id="pinecone_structured_sync",
            action="pinecone_sync.failed",
            resource_type="service",
            resource_id=str(service_id),
            payload={"step": "embedding", "error": str(exc)},
        )
        return False

    if embedding is None:
        logger.warning("[PINE_SYNC] service_id=%s embedding returned None", service_id)
        return False

    # ── Upsert to Pinecone ────────────────────────────────────────────────────
    try:
        pinecone = PineconeClient()
        if not pinecone.is_available():
            logger.warning("[PINE_SYNC] service_id=%s Pinecone not available", service_id)
            return False

        metadata = {
            "clinic_id": settings.clinic_id,
            "service_id": str(service_id),
            "name": svc["name"],
            "version": svc.get("version", 1),
            "updated_at": datetime.utcnow().isoformat(),
            "category": "service",
        }
        await pinecone.upsert_chunk(
            chunk_id=str(service_id),
            embedding=embedding,
            metadata=metadata,
        )
        logger.info(
            "[PINE_SYNC] service_id=%s action=upsert status=success version=%s text_chars=%d",
            service_id, svc.get("version", 1), len(text),
        )
        await audit.log_event(
            actor_type="system",
            actor_id="pinecone_structured_sync",
            action="pinecone_sync.upserted",
            resource_type="service",
            resource_id=str(service_id),
            payload={
                "service_id": str(service_id),
                "name": svc["name"],
                "version": svc.get("version", 1),
                "text_chars": len(text),
            },
        )
        return True

    except Exception as exc:
        logger.error(
            "[PINE_SYNC] service_id=%s action=upsert status=failed error=%s",
            service_id, exc,
        )
        await audit.log_event(
            actor_type="system",
            actor_id="pinecone_structured_sync",
            action="pinecone_sync.failed",
            resource_type="service",
            resource_id=str(service_id),
            payload={"error": str(exc)},
        )
        return False
