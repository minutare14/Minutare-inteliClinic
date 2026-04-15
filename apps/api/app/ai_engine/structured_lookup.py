"""
Structured Data Lookup — Answers questions using internal database records.

Priority 1 in the response chain, BEFORE RAG and LLM.

Handles:
  - Doctor→specialty: "Em qual especialidade a Dra. Ana Paula atende?"
  - Specialty→doctors: "Quais médicos atendem ortopedia?"
  - Insurance catalog: "Quais convênios vocês aceitam?"
  - Clinic address: "Qual o endereço de vocês?"
  - Clinic phone: "Qual o telefone de vocês?"

Decision rules:
  1. doctor_name entity + any specialty/info intent → lookup doctor by name
  2. specialty entity + "quais médicos" question → lookup by specialty
  3. insurance keywords → return insurance catalog
  4. address/location keywords → return ClinicSettings address
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
    if specialty and _matches_any(text_norm, _SPECIALTY_DOCTORS_KW):
        return True
    if _matches_any(text_norm, _INSURANCE_KW):
        return True
    if _matches_any(text_norm, _ADDRESS_KW):
        return True
    if _matches_any(text_norm, _PHONE_KW):
        return True

    return False


class StructuredLookup:
    """
    Priority-1 lookup from structured database records.

    Instantiated in orchestrator.__init__() and called after guardrails,
    before _execute_action() and ResponseComposer.
    """

    def __init__(self, session) -> None:
        from app.repositories.professional_repository import ProfessionalRepository
        self.prof_repo = ProfessionalRepository(session)

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
        if specialty and (
            _matches_any(text_norm, _SPECIALTY_DOCTORS_KW)
            or faro.intent == Intent.LISTAR_ESPECIALIDADES
        ):
            result = await self._lookup_specialty_doctors(specialty)
            if result.answered:
                return result

        # ── Priority 3: Insurance question ────────────────────────────────────
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
            "[STRUCTURED] specialty→doctors: '%s' active_only=True professionals_returned=%d",
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
