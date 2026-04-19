"""
FARO Intent Router — Adapted from minutare.ai FARO module.

Deterministic pre-analysis: keyword intent classification + regex entity extraction.
Produces a structured BRIEF with intent, confidence, entities, missing fields,
and suggested actions.

Future: GLiNER2 NER integration for richer entity extraction.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    AGENDAR = "agendar"
    REMARCAR = "remarcar"
    CANCELAR = "cancelar"
    DUVIDA_OPERACIONAL = "duvida_operacional"
    FALAR_COM_HUMANO = "falar_com_humano"
    POLITICAS = "politicas"
    LISTAR_PROFISSIONAIS = "listar_profissionais"
    LISTAR_ESPECIALIDADES = "listar_especialidades"
    SAUDACAO = "saudacao"
    CONFIRMACAO = "confirmacao"
    DESCONHECIDA = "desconhecida"


@dataclass
class FaroBrief:
    """Structured output from FARO analysis."""
    intent: Intent
    confidence: float
    entities: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    confirmation_detected: bool = False
    suggested_actions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "missing_fields": self.missing_fields,
            "confirmation_detected": self.confirmation_detected,
            "suggested_actions": self.suggested_actions,
        }


# ─── Known medical specialties (for entity extraction + intent boost) ──────────

KNOWN_SPECIALTIES: list[tuple[str, str]] = [
    # (normalized keyword, display name)
    ("ortopedia", "Ortopedia"),
    ("ortopedista", "Ortopedia"),
    ("traumatologia", "Ortopedia"),
    ("cardio", "Cardiologia"),
    ("cardiologia", "Cardiologia"),
    ("cardiologista", "Cardiologia"),
    ("pediatria", "Pediatria"),
    ("pediatra", "Pediatria"),
    ("ginecologia", "Ginecologia"),
    ("ginecologista", "Ginecologia"),
    ("obstetricia", "Obstetrícia"),
    ("obstetra", "Obstetrícia"),
    ("neuro", "Neurologia"),
    ("neurologia", "Neurologia"),
    ("neurologista", "Neurologia"),
    ("dermato", "Dermatologia"),
    ("dermatologia", "Dermatologia"),
    ("dermatologista", "Dermatologia"),
    ("oftalmo", "Oftalmologia"),
    ("oftalmologia", "Oftalmologia"),
    ("oftalmologista", "Oftalmologia"),
    ("psiquiatria", "Psiquiatria"),
    ("psiquiatra", "Psiquiatria"),
    ("uro", "Urologia"),
    ("urologia", "Urologia"),
    ("urologista", "Urologia"),
    ("endo", "Endocrinologia"),
    ("endocrinologia", "Endocrinologia"),
    ("endocrinologista", "Endocrinologia"),
    ("gastro", "Gastroenterologia"),
    ("gastroenterologia", "Gastroenterologia"),
    ("pneumo", "Pneumologia"),
    ("pneumologia", "Pneumologia"),
    ("pneumologista", "Pneumologia"),
    ("reuma", "Reumatologia"),
    ("reumatologia", "Reumatologia"),
    ("reumatologista", "Reumatologia"),
    ("onco", "Oncologia"),
    ("oncologia", "Oncologia"),
    ("oncologista", "Oncologia"),
    ("otorrino", "Otorrinolaringologia"),
    ("otorrinolaringologia", "Otorrinolaringologia"),
    ("clinica geral", "Clínica Geral"),
    ("clinico geral", "Clínica Geral"),
    ("clinica medica", "Clínica Médica"),
    ("medicina geral", "Clínica Geral"),
    ("nutrologia", "Nutrologia"),
    ("nutricionista", "Nutrição"),
    ("nutricao", "Nutrição"),
    ("fisioterapia", "Fisioterapia"),
    ("fisioterapeuta", "Fisioterapia"),
    ("psicologia", "Psicologia"),
    ("psicologo", "Psicologia"),
    ("psicologa", "Psicologia"),
    ("vascular", "Cirurgia Vascular"),
    ("cirurgia", "Cirurgia Geral"),
    ("cirurgiao", "Cirurgia Geral"),
]


# ─── Confirmation patterns (PT-BR) ─────────────────────────────

CONFIRMATION_PATTERNS = [
    r"\bconfirmo\b", r"\bpode\s+marcar\b", r"\bautorizo\b",
    r"\bpode\s+agendar\b", r"\bconfirma\b", r"\bconfirmado\b",
    r"\bsim,?\s*(pode|quero|confirmo)\b", r"\bpode\s+sim\b",
    r"\b(isso|isso\s+mesmo)\b", r"\bpode\s+ser\b",
]

# ─── Intent keywords ────────────────────────────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "agendar": [
        "marcar", "agendar", "quero marcar", "marcar consulta",
        "agendar consulta", "preciso de consulta", "quero consulta",
        "vaga", "disponibilidade",
    ],
    "cancelar": [
        "cancelar", "desmarcar", "cancela", "desistir",
    ],
    "remarcar": [
        "remarcar", "reagendar", "mudar horario", "trocar horario",
        "alterar consulta", "mudar a data", "trocar a data", "adiar",
    ],
    "politicas": [
        "politica", "regra", "regras", "norma",
        "cancelamento", "antecedencia", "documento",
    ],
    "listar_profissionais": [
        "quais medicos", "quais medicas", "quais medicos vocês tem",
        "quais profissionais", "qual medico", "qual médica", "qual médico",
        "que medico", "que médicos", "que profissionais",
        "me diz os medicos", "lista de medicos", "relação de medicos",
        "profissionais disponíveis", "médicos ativos", "equipe médica",
        "quem são os medicos", "quais doctors", "lista médicos",
        "qual a especialidade", "especialidade de cada",
        "quem atende", "quem são vocês", "time da clinica",
        "quais medicos vocês têm", "quais medicos vcs",
        "lista dos medicos", "relação de profissionais",
        "quais dokter", "doktores", "doktor",
        "quais especialidades", "quais as especialidades",
        "qual especialidade", "qual a especialidade de",
        "quais medicos existem", "liste os medicos",
        "relação de medicos", "quais profissonais",
        "qual a equipe", "equipe de profissionais",
        "quem são os profissionais", "quais os medicos",
        "qual a especialidade de cada", "especialidade de cada profissional",
        "profissionais e especialidades", "quais medicos e especialidades",
    ],
    "listar_especialidades": [
        "especialidade", "especialidades", "especialista",
        "quais areas", "que areas", "areas de atendimento",
        "disponiveis na clinica",
    ],
    "duvida_operacional": [
        "horario", "funcionamento", "endereco", "telefone",
        "convenio", "plano", "aceita", "preparo", "exame",
        "valor", "preco", "quanto custa", "como funciona",
        "onde fica", "localizacao", "whatsapp",
    ],
    "falar_com_humano": [
        "atendente", "humano", "pessoa", "recepcao",
        "falar com alguem", "atendimento humano", "quero falar",
    ],
    "saudacao": [
        "oi", "ola", "bom dia", "boa tarde", "boa noite",
        "hey", "hello", "/start", "start", "comecar", "iniciar",
    ],
}

# ─── Date parsing ───────────────────────────────────────────────

DATE_RELATIVE = {
    "hoje": 0, "amanha": 1, "depois de amanha": 2,
}

WEEKDAYS_PT = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sabado": 5, "domingo": 6,
}


def _normalize(text: str) -> str:
    """Remove accents for matching (simple approach)."""
    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a",
        "é": "e", "ê": "e", "í": "i", "ó": "o",
        "ô": "o", "õ": "o", "ú": "u", "ç": "c",
    }
    result = text.lower()
    for src, dst in replacements.items():
        result = result.replace(src, dst)
    return result


def _detect_confirmation(text: str) -> bool:
    """Check if user text contains explicit confirmation."""
    text_lower = text.lower().strip()
    return any(re.search(p, text_lower) for p in CONFIRMATION_PATTERNS)


def _classify_intent(text_norm: str) -> tuple[Intent, float]:
    """
    Keyword scoring for intent classification.
    Returns (intent, confidence).
    Multi-word keywords score higher (word count) to prioritize specific matches.
    """
    scores: dict[str, float] = {}
    for intent_key, keywords in INTENT_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            if kw in text_norm:
                # Multi-word keywords get bonus weight; longer keywords score more
                score += len(kw.split()) + len(kw) * 0.01
        if score > 0:
            scores[intent_key] = score

    # Disambiguation: "remarcar" contains "marcar" — prefer longer keyword match
    if "remarcar" in scores and "agendar" in scores:
        # If text contains "remarcar", the "marcar" match in agendar is a substring
        if "remarcar" in text_norm or "reagendar" in text_norm:
            scores.pop("agendar", None)

    if not scores:
        return Intent.DESCONHECIDA, 0.30

    best_key = max(scores, key=scores.get)
    best_score = scores[best_key]
    confidence = min(0.40 + best_score * 0.08, 0.99)

    try:
        intent = Intent(best_key)
    except ValueError:
        intent = Intent.DESCONHECIDA

    return intent, round(confidence, 2)


def _parse_dates(text_norm: str) -> dict:
    """Extract date and time from text using regex + relative keywords."""
    result: dict = {}
    today = datetime.now().date()

    # Relative dates
    for keyword, offset in DATE_RELATIVE.items():
        if keyword in text_norm:
            result["date"] = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
            break

    # Weekday names
    if "date" not in result:
        for day_name, weekday_num in WEEKDAYS_PT.items():
            if day_name in text_norm:
                days_ahead = (weekday_num - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                result["date"] = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                break

    # Absolute dates: DD/MM or DD/MM/YYYY
    # Find all date matches so we can detect two dates (e.g. rescheduling: "de 10/04 para 20/04")
    all_date_matches = list(re.finditer(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", text_norm))
    for i, date_match in enumerate(all_date_matches[:2]):
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            parsed = datetime(year, month, day).date().strftime("%Y-%m-%d")
            if i == 0 and "date" not in result:
                result["date"] = parsed
            elif i == 1 and "date" in result:
                result["new_date"] = parsed
        except ValueError:
            pass

    # Time: HH:MM, HHh, às HH
    time_match = re.search(
        r"(?:as?\s+)?(\d{1,2})(?::(\d{2})|[hH](?:(\d{2}))?|\s*horas?)", text_norm
    )
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or time_match.group(3) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result["time"] = f"{hour:02d}:{minute:02d}"

    return result


def _extract_specialty(text_norm: str, specialties_override: list[str] | None = None) -> str | None:
    """Extract medical specialty from text. DB specialties checked first, then hardcoded list."""
    if specialties_override:
        for name in specialties_override:
            if name.lower() in text_norm:
                return name
    for keyword, display in KNOWN_SPECIALTIES:
        if keyword in text_norm:
            return display
    return None


def _extract_entities(text_norm: str, specialties_override: list[str] | None = None) -> dict:
    """
    Simple entity extraction (regex-based).
    Future: integrate GLiNER2 for ML-based NER.
    """
    entities: dict = {}

    # CPF
    cpf_match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text_norm)
    if cpf_match:
        entities["cpf"] = cpf_match.group()

    # Email
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text_norm)
    if email_match:
        entities["email"] = email_match.group()

    # Phone
    phone_match = re.search(r"(?:\+55\s?)?\(?\d{2}\)?\s?\d{4,5}-?\d{4}", text_norm)
    if phone_match:
        entities["phone"] = phone_match.group()

    # Doctor name (Dr./Dra. pattern) — stop at prepositions/common words
    doc_match = re.search(
        r"(?:dr\.?|dra\.?)\s+([a-z]{2,}(?:\s+(?!para|de|do|da|no|na|em|com|por|as?|os?)[a-z]{2,})*)",
        text_norm,
    )
    if doc_match:
        entities["doctor_name"] = doc_match.group(1).title()

    # Medical specialty
    specialty = _extract_specialty(text_norm, specialties_override)
    if specialty:
        entities["specialty"] = specialty

    # Date/time
    dates = _parse_dates(text_norm)
    entities.update(dates)

    return entities


def _compute_missing_fields(intent: Intent, entities: dict) -> list[str]:
    """Determine required fields not yet provided."""
    missing: list[str] = []
    if intent == Intent.AGENDAR:
        if "doctor_name" not in entities and "specialty" not in entities:
            missing.append("especialidade_ou_medico")
        if "date" not in entities:
            missing.append("data_preferencia")
    elif intent == Intent.CANCELAR:
        if "date" not in entities:
            missing.append("referencia_consulta")
    elif intent == Intent.REMARCAR:
        if "date" not in entities:
            missing.append("nova_data")
    return missing


def _suggest_actions(intent: Intent, entities: dict) -> list[dict]:
    """Suggest system actions based on intent and available entities."""
    suggestions: list[dict] = []

    if intent == Intent.AGENDAR:
        if entities.get("date"):
            suggestions.append({
                "action": "search_slots",
                "args": {k: v for k, v in entities.items() if k in ("date", "time", "doctor_name")},
                "risk": "read",
            })
    elif intent == Intent.LIST_PROFISSIONAIS:
        suggestions.append({"action": "list_professionals", "args": {}, "risk": "read"})
    elif intent == Intent.LISTAR_ESPECIALIDADES:
        suggestions.append({"action": "list_specialties", "args": {}, "risk": "read"})
    elif intent == Intent.POLITICAS:
        suggestions.append({"action": "clinic_policies", "args": {}, "risk": "read"})
    elif intent == Intent.DUVIDA_OPERACIONAL:
        suggestions.append({"action": "rag_query", "args": {}, "risk": "read"})

    return suggestions


def analyze(text: str, specialties_override: list[str] | None = None) -> FaroBrief:
    """
    Full FARO analysis on a user message.
    Returns a structured FaroBrief.

    specialties_override: specialty names from ClinicSpecialties DB table.
    When provided, they are matched first before the hardcoded KNOWN_SPECIALTIES list.
    """
    text_norm = _normalize(text)

    # 1. Detect confirmation
    confirmation = _detect_confirmation(text)

    if confirmation:
        return FaroBrief(
            intent=Intent.CONFIRMACAO,
            confidence=0.95,
            confirmation_detected=True,
        )

    # 2. Extract entities
    entities = _extract_entities(text_norm, specialties_override)

    # 3. Classify intent
    intent, confidence = _classify_intent(text_norm)

    # 4. Boost confidence if entities align with intent
    if intent == Intent.AGENDAR and (entities.get("date") or entities.get("doctor_name")):
        confidence = min(confidence + 0.15, 0.99)
    if intent == Intent.REMARCAR and entities.get("date"):
        confidence = min(confidence + 0.10, 0.99)

    # 4b. Specialty detected — decide between informational and scheduling intent.
    #
    # "tem neuro?" / "vocês tem cardiologista?" → LIST_PROFISSIONAIS (asking about available doctors)
    # "quais especialidades vocês oferecem?" → LISTAR_ESPECIALIDADES
    # AGENDAR + specialty → boost confidence (already correctly classified)
    #
    if entities.get("specialty"):
        if intent == Intent.DESCONHECIDA:
            # "tem neuro?", "vocês tem cardiologista?", "tem ortopedista?"
            # → user wants to know which doctors are available in that specialty
            intent = Intent.LIST_PROFISSIONAIS
            confidence = 0.80
        elif intent == Intent.AGENDAR:
            confidence = min(confidence + 0.10, 0.99)
        elif intent == Intent.LIST_PROFISSIONAIS:
            confidence = min(confidence + 0.10, 0.99)

    # 5. Missing fields
    missing = _compute_missing_fields(intent, entities)

    # 6. Suggested actions
    actions = _suggest_actions(intent, entities)

    return FaroBrief(
        intent=intent,
        confidence=round(confidence, 2),
        entities=entities,
        missing_fields=missing,
        confirmation_detected=False,
        suggested_actions=actions,
    )
