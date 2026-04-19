"""
Cleanup script — apaga histórico de conversas e traces do LangSmith.

Uso:
  python scripts/cleanup_history.py [--dry-run]

Cuidado:
  - Apaga TODAS as mensagens e conversas do banco (sem recuperação)
  - Apaga TODOS os runs do projeto LangSmith (sem recuperação)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def clear_database():
    """Truncate messages e conversations do banco PostgreSQL."""
    from app.core.db import async_session
    from sqlalchemy import text

    logger.info("[DB] Conectando ao banco...")
    async with async_session() as session:
        # 1. Apagar handoffs primeiro (FK)
        result = await session.execute(text("SELECT COUNT(*) FROM handoffs"))
        count = result.scalar() or 0
        await session.execute(text("TRUNCATE handoffs CASCADE"))
        logger.info("[DB] Handoffs apagados: %d registros", count)

        # 2. Apagar messages
        result = await session.execute(text("SELECT COUNT(*) FROM messages"))
        count = result.scalar() or 0
        await session.execute(text("TRUNCATE messages CASCADE"))
        logger.info("[DB] Mensagens apagadas: %d registros", count)

        # 3. Apagar conversations
        result = await session.execute(text("SELECT COUNT(*) FROM conversations"))
        count = result.scalar() or 0
        await session.execute(text("TRUNCATE conversations CASCADE"))
        logger.info("[DB] Conversas apagadas: %d registros", count)

        await session.commit()
        logger.info("[DB] Histórico do banco apagado com sucesso.")


def clear_langsmith():
    """Apaga todos os runs do projeto LangSmith configurado."""
    from app.core.config import settings
    from langsmith import Client

    if not settings.langsmith_enabled or not settings.langsmith_api_key:
        logger.warning("[LANG] LangSmith não está ativo — pulando")
        return

    logger.info(
        "[LANG] Apagando runs do projeto '%s'...",
        settings.langsmith_project,
    )
    client = Client(
        api_key=settings.langsmith_api_key,
        endpoint=settings.langsmith_endpoint,
    )
    client.delete_project(project_name=settings.langsmith_project)
    logger.info("[LANG] Runs apagados com sucesso.")


def main():
    parser = argparse.ArgumentParser(description="Limpa histórico do bot e traces LangSmith")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem executar",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("[DRY RUN] Nada será executado.")
        logger.info("[DRY RUN] Ações que seriam feitas:")
        logger.info("[DRY RUN]   1. TRUNCATE CASCADE em handoffs, messages, conversations")
        logger.info(
            "[DRY RUN]   2. LangSmith delete_project('%s')",
            os.getenv("LANGSMITH_PROJECT", "inteliclinic-runtime"),
        )
        return

    logger.info("=" * 60)
    logger.info("  ATENÇÃO: este script IRREVOGAVELMENTE apaga dados!")
    logger.info("  - Todas as mensagens e conversas do bot")
    logger.info("  - Todos os traces do LangSmith")
    logger.info("=" * 60)
    confirm = input("\nDigite 'SIM' para confirmar: ")
    if confirm != "SIM":
        logger.info("Abortado pelo usuário.")
        return

    clear_langsmith()
    asyncio.run(clear_database())

    logger.info("Done.")


if __name__ == "__main__":
    main()
