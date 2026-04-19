"""
Structured Data Lookup — Answers questions using internal database records.

Priority 1 in the response chain, BEFORE RAG and LLM.

Handles:
  - Doctor→specialty: "Em qual especialidade a Dra. Ana Paula atende?"
  - Specialty→doctors: "Quais médicos atendem ortopedia?"
  - Service→price: "Quanto custa a consulta neurológica?"
  - Service→doctor: "Quem faz peeling químico?"
  - Insurance catalog: "Quais convênios vocês aceitam?"
  - Clinic address: "Qual o endereço de vocês?"
  - Clinic phone: "Qual o telefone de vocês?"
  - Opening hours: "Qual o horário de atendimento?"
  - Prices: "Quanto custa uma consulta?"

Decision rules:
  1. doctor_name entity + any specialty/info intent → lookup doctor by name
  2. specialty entity + "quais médicos" question → lookup by specialty
  3. service keywords → lookup service price/doctor/rule from structured tables
  4. insurance keywords → return insurance catalog
  5. address/location keywords → return ClinicSettings address
  6. phone keywords → return ClinicSettings phone
  7. hours keywords → return opening hours
  8. price keywords → return service price from structured tables

CRITICAL: Prices, doctors, rules, and availability ALWAYS come from structured
tables first. Pinecone is only a semantic fallback for open-ended questions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai_engine.intent_router import FaroBrief, Intent

logger = logging.getLogger(__name__)


@dataclass
class LookupResult:
    """Result of a structured data lookup attempt."""
    answered: bool
    text: str
    source: str  # "professionals" | "insurance_catalog" | "clinic_settings" | "none"


# ─── Keyword sets for question-type detection ─────────────────────────────────

_DOCTOR_SPECIALTY_KW = {
    "qual especialidade", "que especialidade", "especialidade atende",
    "atende qual", "em qual area", "area de atuacao", "atua em",
}

_SPECIALTY_DOCTORS_KW = {
    "quais medicos", "quem atende", "qual medico",
    "tem medico", "tem doutor", "tem dra", "tem dr",
    "profissional em", "profissionais de",
    "quais sao", "quais sao os", "me mostra",
    "quais neurologistas", "quais cardiologistas",
    "listar", "mostra os", "quais profissionais",
}

_INSURANCE_KW = {
    "convenio", "plano", "aceita", "aceitar", "aceito",
    "convenios", "planos", "aceita plano", "plano de saude",
    "unimed", "bradesco saude", "amil", "sulamerica",
    "hapvida", "notredame", "gndi",
}

_ADDRESS_KW = {
    "endereco", "localizacao", "onde fica", "onde voces ficam",
    "onde voces estao", "como chegar", "como chego",
    "qual o endereco", "qual endereco", "onde sao",
}

_PHONE_KW = {
    "telefone", "contato", "numero", "ligar", "whatsapp",
    "qual o numero", "como falar", "como entrar em contato",
}

_HOURS_KW = {
    "horario", "horarios", "horrio", "hrs",
    "fecha", "fechamos", "fecha que horas",
    "abre", "abrimos", "abre que horas",
    "funciona", "funcionamento", "atendimento",
    "da clinica", "do consultorio",
    "sabado", "sbado", "domingo",
}

_PRICE_KW = {
    "preco", "preco", "precos", "valor",
    "quanto custa", "quanto cobra", "quanto é",
    "tabela", "mais barato", "caro", "barato",
    "orcamento", "consulta", "sessao",
}

_SERVICE_KW = {
    "consulta", "retorno", "procedimento", "exame",
    "atendimento", "servico",
    "triagem", "orientacao",
}


def _normalize(text: str) -> str:
    """Remove accents for keyword matching."""
    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a",
        "é": "e", "ê": "e", "í": "i", "ó": "o",
        "ô": "o", "õ": "o", "ú": "u", "ç": "c",
    }
    result = text.lower()
    for src, dst in replacements.items():
        result = result.replace(src, dst)
    return result


def _matches_any(text_norm: str, keywords: set[str]) -> bool:
    return any(kw in text_norm for kw in keywords)


# Transactional intents that should NEVER be intercepted by structured lookup.
# These always go through the action execution pipeline.
_TRANSACTIONAL_INTENTS = {
    Intent.AGENDAR,
    Intent.CANCELAR,
    Intent.REMARCAR,
    Intent.CONFIRMACAO,
    Intent.FALAR_COM_HUMANO,
}


def _is_structured_query(user_text: str, faro: FaroBrief) -> bool:
    """
    Returns True if the query is likely answerable from structured data.
    Used to decide whether to run structured lookup before RAG.

    Never intercepts transactional intents (AGENDAR, CANCELAR, etc.).
    """
    if faro.intent in _TRANSACTIONAL_INTENTS:
        return False

    text_norm = _normalize(user_text)
    entities = faro.entities
    doctor_name = entities.get("doctor_name")
    specialty = entities.get("specialty")

    if doctor_name:
        return True  # informational question about a specific doctor

    # If a specialty entity was extracted, always route to structured lookup.
    # This catches colloquial questions like "tem algum neuro?" / "tem ortopedista?"
    # even without explicit "quais medicos" keywords.
    if specialty:
        return True

    if _matches_any(text_norm, _SERVICE_KW):
        return True
    if _matches_any(text_norm, _PRICE_KW):
        return True
    if _matches_any(text_norm, _INSURANCE_KW):
        return True
    if _matches_any(text_norm, _ADDRESS_KW):
        return True
    if _matches_any(text_norm, _PHONE_KW):
        return True
    if _matches_any(text_norm, _HOURS_KW):
        return True

    return False


class StructuredLookup:
    """
    Priority-1 lookup from structured database records.

    Instantiated in orchestrator.__init__() and called after guardrails,
    before _execute_action() and ResponseComposer.

    Priority order:
      1. Doctor → specialty (most specific)
      2. Specialty → doctors list
      3. Service → price/doctor/rule (from ServiceRepository)
      4. Insurance catalog
      5. Clinic address
      6. Clinic phone/contact
      7. Opening hours
      8. Prices (from ServiceRepository — NOT RAG)
    """

    # Intents that are listing requests (handled by StructuredLookup)
    _LISTING_INTENTS = {
        Intent.LISTAR_PROFISSIONAIS,
        Intent.LISTAR_ESPECIALIDADES,
    }

    def __init__(self, session, rag_svc: "RagService | None" = None) -> None:
        from app.repositories.professional_repository import ProfessionalRepository
        from app.repositories.service_repository import ServiceRepository
        self.prof_repo = ProfessionalRepository(session)
        self.svc_repo = ServiceRepository(session)
        self.rag_svc = rag_svc
        self._session = session

    async def lookup(
        self,
        user_text: str,
        faro: FaroBrief,
        clinic_cfg=None,
        insurance_items: list | None = None,
    ) -> LookupResult:
        """
        Try to answer query from structured data.

        Returns LookupResult(answered=True, ...) if handled,
        or LookupResult(answered=False, ...) to fall through to RAG/LLM.

        NEVER intercepts transactional intents (AGENDAR, CANCELAR, REMARCAR, etc.).
        Those always go through the action execution pipeline.

        Priority order:
          1. Doctor → specialty (most specific)
          2. Specialty → doctors list
          3. Insurance catalog
          4. Clinic address
          5. Clinic phone/contact
        """
        # Skip entirely for transactional intents
        if faro.intent in _TRANSACTIONAL_INTENTS:
            return LookupResult(answered=False, text="", source="none")

        text_norm = _normalize(user_text)
        entities = faro.entities
        doctor_name = entities.get("doctor_name")
        specialty = entities.get("specialty")

        # ── Priority 1: Specific doctor's specialty ───────────────────────────
        # "Em qual especialidade a Dra. Ana Paula atende?"
        # "Dr. João Santos atende qual especialidade?"
        if doctor_name:
            result = await self._lookup_doctor_specialty(doctor_name, text_norm, faro)
            if result.answered:
                return result

        # ── Priority 2: Which doctors attend a specialty ──────────────────────
        # "Quais médicos atendem ortopedia?"
        # "Tem médico de cardiologia?"
        # "tem neuro?" (specialty detected + LISTAR_PROFISSIONAIS)
        if specialty and (
            _matches_any(text_norm, _SPECIALTY_DOCTORS_KW)
            or faro.intent == Intent.LISTAR_ESPECIALIDADES
            or faro.intent == Intent.LISTAR_PROFISSIONAIS
        ):
            result = await self._lookup_specialty_doctors(specialty)
            if result.answered:
                return result

        # ── Priority 2b: Service lookup (price, doctor, rule) ───────────────
        # "quanto custa consulta neurológica?"
        # "quem faz peeling?"
        # "qual o valor da consulta?"
        if _matches_any(text_norm, _PRICE_KW) or _matches_any(text_norm, _SERVICE_KW):
            result = await self._lookup_service(text_norm, specialty, insurance_items or [])
            if result.answered:
                return result

        # ── Priority 3: List ALL professionals (no filter) ────────────────────
        # "quais médicos vocês têm?", "liste os profissionais"
        if faro.intent == Intent.LISTAR_PROFISSIONAIS:
            result = await self._lookup_all_professionals()
            if result.answered:
                return result

        # ── Priority 4: Insurance question ────────────────────────────────────
        # "Quais convênios vocês aceitam?"
        # "Aceitam Unimed?"
        if _matches_any(text_norm, _INSURANCE_KW):
            return self._lookup_insurance(insurance_items or [])

        # ── Priority 4: Clinic address ────────────────────────────────────────
        # "Qual o endereço de vocês?"
        if _matches_any(text_norm, _ADDRESS_KW):
            return self._lookup_address(clinic_cfg)

        # ── Priority 5: Clinic phone / contact ───────────────────────────────
        # "Qual o telefone de vocês?"
        if _matches_any(text_norm, _PHONE_KW):
            return self._lookup_phone(clinic_cfg)

        # ── Priority 6: Opening hours ─────────────────────────────────────────
        # "Qual o horário de atendimento?", "Vocês abrem aos sábados?"
        if _matches_any(text_norm, _HOURS_KW):
            return self._lookup_hours(clinic_cfg)

        # ── Priority 7: Prices / procedure costs ──────────────────────────────
        # "Quanto custa uma consulta?", "Tem tabela de preços?"
        if _matches_any(text_norm, _PRICE_KW):
            return await self._lookup_prices()

        return LookupResult(answered=False, text="", source="none")

    # ─── Private lookup methods ───────────────────────────────────────────────

    async def _lookup_doctor_specialty(
        self, doctor_name: str, text_norm: str, faro: FaroBrief
    ) -> LookupResult:
        """Find a specific doctor's specialty from the professionals table."""
        try:
            profs = await self.prof_repo.search_by_name(doctor_name)
        except Exception:
            logger.exception("[STRUCTURED] Falha ao buscar profissional '%s'", doctor_name)
            return LookupResult(answered=False, text="", source="professionals")

        logger.info(
            "[STRUCTURED] doctor→search: name='%s' active_only=True professionals_returned=%d",
            doctor_name, len(profs),
        )
        if not profs:
            logger.info("[STRUCTURED] Profissional '%s' não encontrado no banco (active_only=True)", doctor_name)
            # Return answered=True so we don't fall through to generic template
            return LookupResult(
                answered=True,
                text=(
                    f"Não encontrei um profissional com o nome *{doctor_name}* cadastrado. "
                    "Quer que eu liste os profissionais disponíveis?"
                ),
                source="professionals",
            )

        if len(profs) == 1:
            p = profs[0]
            # Decide response based on question type
            is_specialty_question = (
                _matches_any(text_norm, _DOCTOR_SPECIALTY_KW)
                or faro.intent == Intent.LISTAR_ESPECIALIDADES
                or "especialidade" in text_norm
            )
            if is_specialty_question:
                text = f"*{p.full_name}* atende na especialidade de *{p.specialty}*."
            else:
                # General question about the doctor
                text = f"*{p.full_name}* — especialidade: {p.specialty}."
                if hasattr(p, "crm") and p.crm:
                    text += f" CRM: {p.crm}."

            logger.info(
                "[STRUCTURED] doctor→specialty: '%s' → '%s' (source=professionals)",
                p.full_name, p.specialty,
            )
            return LookupResult(answered=True, text=text, source="professionals")

        # Multiple matches — list them
        lines = [f"Encontrei mais de um profissional com o nome *{doctor_name}*:\n"]
        for p in profs:
            lines.append(f"• {p.full_name} — {p.specialty}")
        lines.append("\nPode especificar o nome completo?")
        return LookupResult(answered=True, text="\n".join(lines), source="professionals")

    async def _lookup_specialty_doctors(self, specialty: str) -> LookupResult:
        """Find all ACTIVE doctors in a given specialty (active_only=True)."""
        try:
            profs = await self.prof_repo.list_active(specialty)
        except Exception:
            logger.exception("[STRUCTURED] Falha ao buscar profissionais por especialidade '%s'", specialty)
            return LookupResult(answered=False, text="", source="professionals")

        logger.info(
            "[STRUCTURED] specialty→doctors: specialty='%s' active_only=True professionals_returned=%d",
            specialty, len(profs),
        )

        if not profs:
            # Return answered=True so we don't fall through to RAG with potentially stale data.
            # The source-of-truth is the live DB: this specialty has no active doctors right now.
            return LookupResult(
                answered=True,
                text=(
                    f"No momento não temos profissionais ativos em *{specialty}*. "
                    "Posso listar as especialidades disponíveis se preferir."
                ),
                source="professionals",
            )

        if len(profs) == 1:
            p = profs[0]
            text = f"Sim! Temos *{p.full_name}* atendendo em *{specialty}*."
        else:
            lines = [f"Profissionais que atendem *{specialty}*:\n"]
            for p in profs:
                lines.append(f"• {p.full_name}")
            text = "\n".join(lines)

        return LookupResult(answered=True, text=text, source="professionals")

    async def _lookup_all_professionals(self) -> LookupResult:
        """List ALL active professionals with name and specialty."""
        try:
            profs = await self.prof_repo.list_active()
        except Exception:
            logger.exception("[STRUCTURED] Falha ao buscar profissionais (list_all)")
            return LookupResult(answered=False, text="", source="professionals")

        logger.info(
            "[STRUCTURED] list_professionals: returned=%d",
            len(profs),
        )

        if not profs:
            return LookupResult(
                answered=True,
                text="No momento não há profissionais ativos cadastrados.",
                source="professionals",
            )

        # Group by specialty for cleaner output
        by_specialty: dict[str, list] = {}
        for p in profs:
            by_specialty.setdefault(p.specialty, []).append(p.full_name)

        lines = ["Profissionais disponíveis:\n"]
        for specialty, names in sorted(by_specialty.items()):
            names_str = ", ".join(names)
            lines.append(f"• *{specialty}*: {names_str}")

        text = "\n".join(lines)
        return LookupResult(answered=True, text=text, source="professionals")

    def _lookup_insurance(self, insurance_items: list) -> LookupResult:
        """Return insurance catalog from admin table."""
        if not insurance_items:
            logger.info("[STRUCTURED] insurance lookup: 0 convenios cadastrados")
            return LookupResult(
                answered=True,
                text=(
                    "No momento nao encontrei convenios ativos cadastrados no banco da clinica. "
                    "Posso encaminhar sua duvida para a equipe, se quiser."
                ),
                source="insurance_catalog",
            )

        names = [i.name for i in insurance_items]
        text = (
            "Convênios e planos aceitos:\n\n"
            + "\n".join(f"• {n}" for n in names)
            + "\n\nPara confirmar cobertura, recomendamos verificar com sua operadora."
        )
        logger.info("[STRUCTURED] insurance lookup: %d convênios (source=insurance_catalog)", len(names))
        return LookupResult(answered=True, text=text, source="insurance_catalog")

    def _lookup_address(self, clinic_cfg) -> LookupResult:
        """Return clinic address from ClinicSettings."""
        if not clinic_cfg:
            logger.info("[STRUCTURED] address lookup: clinic settings ausente")
            return LookupResult(
                answered=True,
                text="Ainda nao tenho o endereco cadastrado no banco da clinica.",
                source="clinic_settings",
            )

        parts = []
        if getattr(clinic_cfg, "address", None):
            parts.append(clinic_cfg.address)
        if getattr(clinic_cfg, "city", None):
            parts.append(clinic_cfg.city)
        if getattr(clinic_cfg, "state", None):
            parts.append(clinic_cfg.state)
        if getattr(clinic_cfg, "zip_code", None):
            parts.append(f"CEP {clinic_cfg.zip_code}")

        if not parts:
            return LookupResult(
                answered=True,
                text="Ainda nao tenho o endereco cadastrado no banco da clinica.",
                source="clinic_settings",
            )

        clinic_name = getattr(clinic_cfg, "name", None) or "nossa clínica"
        text = f"Endereço de *{clinic_name}*:\n\n📍 {', '.join(parts)}"
        phone = getattr(clinic_cfg, "phone", None)
        if phone:
            text += f"\n📞 {phone}"

        logger.info("[STRUCTURED] address lookup (source=clinic_settings)")
        return LookupResult(answered=True, text=text, source="clinic_settings")

    def _lookup_phone(self, clinic_cfg) -> LookupResult:
        """Return clinic phone from ClinicSettings."""
        if not clinic_cfg:
            logger.info("[STRUCTURED] phone lookup: clinic settings ausente")
            return LookupResult(
                answered=True,
                text="Ainda nao tenho telefone ou contato cadastrado no banco da clinica.",
                source="clinic_settings",
            )

        phone = getattr(clinic_cfg, "phone", None)
        if not phone:
            return LookupResult(
                answered=True,
                text="Ainda nao tenho telefone ou contato cadastrado no banco da clinica.",
                source="clinic_settings",
            )

        clinic_name = getattr(clinic_cfg, "name", None) or "nossa clínica"
        text = f"Telefone / contato de *{clinic_name}*:\n\n📞 {phone}"
        logger.info("[STRUCTURED] phone lookup (source=clinic_settings)")
        return LookupResult(answered=True, text=text, source="clinic_settings")

    def _lookup_hours(self, clinic_cfg) -> LookupResult:
        """Return clinic opening hours from ClinicSettings."""
        # Try to get hours from clinic_cfg if available
        hours_text = None
        if clinic_cfg:
            hours_text = getattr(clinic_cfg, "opening_hours", None)
            if not hours_text:
                hours_text = getattr(clinic_cfg, "hours", None)

        if hours_text:
            clinic_name = getattr(clinic_cfg, "name", None) or "nossa clínica"
            text = f"Horário de atendimento de *{clinic_name}*:\n\n{hours_text}"
            logger.info("[STRUCTURED] hours lookup from clinic_settings")
            return LookupResult(answered=True, text=text, source="clinic_settings")

        # Default fallback with general info
        default_text = (
            "Nosso horário de atendimento é:\n\n"
            "• Segunda a sexta: das 8h às 18h\n"
            "• Sábado: das 8h às 12h\n"
            "• Domingo: fechado\n\n"
            "Para informações sobre horários específicos de profissionais, "
            "consulte a agenda disponível."
        )
        logger.info("[STRUCTURED] hours lookup: using default fallback")
        return LookupResult(answered=True, text=default_text, source="structured_lookup")

    # ── Service lookup (prices, doctors, rules from structured tables) ───────

    async def _lookup_service(
        self, text_norm: str, specialty: str | None, insurance_items: list
    ) -> LookupResult:
        """
        Answer questions about services, prices, and who performs them.

        Uses ServiceRepository as source of truth — NOT RAG.
        RAG is only a fallback for supplementary context.
        """
        from app.core.config import settings

        # Try to match service by name keywords or specialty
        matched_services = await self.svc_repo.find_service_by_keywords(
            settings.clinic_id, text_norm
        )

        # If a specialty was extracted, filter by it
        if specialty and matched_services:
            filtered = [s for s in matched_services if specialty.lower() in s["name"].lower()]
            if filtered:
                matched_services = filtered

        if not matched_services:
            return LookupResult(answered=False, text="", source="none")

        # Build response from matched services
        lines = []
        for svc in matched_services[:3]:
            lines.append(f"*{svc['name']}*")
            if svc.get("description"):
                lines.append(f"  {svc['description']}")
            if svc.get("base_price") is not None:
                lines.append(f"  💰 Valor: R$ {svc['base_price']:,.2f}")
            if svc.get("ai_summary"):
                lines.append(f"  ℹ️ {svc['ai_summary']}")
            if svc.get("doctors"):
                names = [d["full_name"] for d in svc["doctors"]]
                lines.append(f"  👨‍⚕️ Atendimento: {', '.join(names)}")
            if svc.get("rules"):
                for rtype, rtext in svc["rules"].items():
                    if rtext:
                        lines.append(f"  📋 {rtype}: {rtext}")
            lines.append("")

        text = "\n".join(lines).strip()
        if not text:
            return LookupResult(answered=False, text="", source="none")

        logger.info(
            "[STRUCTURED:SERVICE] matched=%d text_chars=%d source=structured_service",
            len(matched_services), len(text),
        )
        return LookupResult(answered=True, text=text, source="structured_service")

    async def _lookup_prices(self) -> LookupResult:
        """Return price/cost information from ServiceRepository (structured tables).

        CRITICAL: Always uses structured tables as primary source.
        RAG is only a semantic fallback for supplementary context.
        NEVER uses Pinecone/RAG as primary source for prices.
        """
        # Try structured tables first (ServiceRepository)
        from app.core.config import settings

        try:
            services = await self.svc_repo.list_services_with_prices(settings.clinic_id)
            if services:
                lines = ["Serviços e valores disponíveis:\n"]
                for svc in services:
                    price_str = f"R$ {svc['base_price']:,.2f}" if svc.get("base_price") is not None else "consulte"
                    doctor_str = ""
                    if svc.get("doctors"):
                        names = [d["full_name"] for d in svc["doctors"]]
                        doctor_str = f" ({', '.join(names)})"
                    lines.append(f"• {svc['name']}: {price_str}{doctor_str}")
                text = "\n".join(lines)
                logger.info(
                    "[STRUCTURED:PRICE] services=%d source=structured_service",
                    len(services),
                )
                return LookupResult(answered=True, text=text, source="structured_service")
        except Exception:
            logger.exception("[STRUCTURED:PRICE] structured lookup failed — falling to RAG")

        # RAG fallback ONLY for supplementary context
        if self.rag_svc is not None:
            try:
                rows = await self.rag_svc.text_search(
                    "preço tabela custo procedimento consulta",
                    top_k=5,
                    category="pricing",
                )
                if rows:
                    lines = ["Informações de preços encontradas (contexto complementar):\n"]
                    for r in rows:
                        snippet = r.content[:300] if hasattr(r, "content") else ""
                        lines.append(f"• {r.title}: {snippet}")
                    logger.info("[STRUCTURED:PRICE] via RAG: %d results (supplementary only)", len(rows))
                    return LookupResult(answered=True, text="\n".join(lines), source="rag_pricing")
            except Exception:
                pass

        # Absolute fallback — structured default
        default_text = (
            "Os valores podem variar conforme o profissional e o convênio. "
            "Para informações precisas sobre o serviço que você procura, "
            "por favor pergunte especificamente pelo nome do serviço ou especialidade."
        )
        logger.info("[STRUCTURED:PRICE] using absolute fallback")
        return LookupResult(answered=True, text=default_text, source="structured_lookup")


