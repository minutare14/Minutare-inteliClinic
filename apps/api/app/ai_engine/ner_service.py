"""
NER Service — GLiNER wrapper with greedy fallback.

Uses GLiNER (urchade/gliner-multilingual-v2.5) for entity extraction when available,
falls back to regex-based greedy detection otherwise.

Entity types detected:
- professional_name, specialty, insurance_plan, service_name
- date_reference, time_period, clinic_info_topic, greeting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENTITY_LABELS = [
    "professional_name",
    "specialty",
    "insurance_plan",
    "service_name",
    "date_reference",
    "time_period",
    "clinic_info_topic",
    "greeting",
]

# Portuguese greeting patterns
_GREETING_PATTERNS = [
    re.compile(r"^\s*(oi|olá|ola|ei|e aí|eaí|opa|bom dia|boa tarde|boa noite|hey|hi|hello|tudo bem|começar|vc é um|vocês são|bot)\b", re.I),
    re.compile(r"\b(oi|olá|ola|ei|e aí|eaí|opa|bom dia|boa tarde|boa noite|hey|hi|hello|tudo bem|começar|vc é um|vocês são|bot)\s*[!,.\-]*\s*$", re.I),
]

# Professional name patterns
_PROFESSIONAL_PATTERNS = [
    re.compile(r"\bDr[.\s]+([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÈÌÒÙÇa-záéíóúãõâêîôûàèìòùç]+)", re.I),
    re.compile(r"\bDra[.\s]+([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÈÌÒÙÇa-záéíóúãõâêîôûàèìòùç]+)", re.I),
    re.compile(r"\bMédic[oa]\s+([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÈÌÒÙÇa-záéíóúãõâêîôûàèìòùç]+)", re.I),
    re.compile(r"\bDr\b", re.I),
]

# Specialty patterns (normalized via _normalize_specialty)
_SPECIALTY_PATTERNS = [
    re.compile(r"\b(clínico geral|clínica geral|clinico geral)\b", re.I),
    re.compile(r"\b(pediatria|pediatra)\b", re.I),
    re.compile(r"\b(ginecologia|ginecologista|obstetrícia|obstetra)\b", re.I),
    re.compile(r"\b(dermatologia|dermatologista)\b", re.I),
    re.compile(r"\b(cardiologia|cardiologista)\b", re.I),
    re.compile(r"\b(neurologia|neurologista)\b", re.I),
    re.compile(r"\b(ortopedia|ortopedista|traumatologia)\b", re.I),
    re.compile(r"\b(oftalmologia|oftalmologista)\b", re.I),
    re.compile(r"\b(psicologia|psicólogo|psicóloga)\b", re.I),
    re.compile(r"\b(psiquiatria|psiquiatra)\b", re.I),
    re.compile(r"\b(endocrinologia|endocrinologista)\b", re.I),
    re.compile(r"\b(gastroenterologia|gastroenterologista)\b", re.I),
    re.compile(r"\b(urologia|urologista)\b", re.I),
    re.compile(r"\b(geriatria|geriatra)\b", re.I),
    re.compile(r"\b(pneumologia|pneumologista)\b", re.I),
    re.compile(r"\b(reumatologia|reumatologista)\b", re.I),
    re.compile(r"\b(alergologia|alergista|imunologia|imunologista)\b", re.I),
    re.compile(r"\b(oncologia|oncologista)\b", re.I),
    re.compile(r"\b(cirurgia|cirurgião|cirurgiã)\b", re.I),
    re.compile(r"\b(radiologia|radiologista)\b", re.I),
    re.compile(r"\b(anestesiologia|anestesiologista)\b", re.I),
    re.compile(r"\b(medicina\s+do\s+trabalho)\b", re.I),
    re.compile(r"\b(estética\s+médica)\b", re.I),
    re.compile(r"\b(nutrologia|nutrologista)\b", re.I),
    re.compile(r"\b(geral)\b", re.I),
    # "de [especialidade]" construction: "médico de cardiologia", "especialista de neurologia"
    re.compile(r"\bde\s+(cardiologia|cardiologista)\b", re.I),
    re.compile(r"\bde\s+(neurologia|neurologista|neuro)\b", re.I),
    re.compile(r"\bde\s+(ortopedia|ortopedista|ortop)\b", re.I),
    re.compile(r"\bde\s+(dermatologia|dermatologista|dermato)\b", re.I),
    re.compile(r"\bde\s+(pediatria|pediatra|pedia)\b", re.I),
    re.compile(r"\bde\s+(ginecologia|ginecologista|gineco)\b", re.I),
    re.compile(r"\bde\s+(oftalmologia|oftalmologista|oftalmo)\b", re.I),
    re.compile(r"\bde\s+(endocrinologia|endocrinologista|endocrino)\b", re.I),
]

# Insurance plan patterns
_INSURANCE_PATTERNS = [
    re.compile(r"\b(Unimed)\b", re.I),
    re.compile(r"\b(Bradesco\s+Saúde|Bradesco\s+Saude)\b", re.I),
    re.compile(r"\b(Amil)\b", re.I),
    re.compile(r"\b(SulAmérica|SulAmerica)\b", re.I),
    re.compile(r"\b(Bassili)\b", re.I),
    re.compile(r"\b(Porto\s+Seguro)\b", re.I),
    re.compile(r"\b(NotreDame|Notre\s*Dame)\b", re.I),
    re.compile(r"\b(Omni)\b", re.I),
    re.compile(r"\b(qual\s+(?:plano|convênio|carência))\b", re.I),
]

# Service name patterns
_SERVICE_PATTERNS = [
    re.compile(r"\b(consulta|atendimento)\b", re.I),
    re.compile(r"\b(exame\w*|exames)\b", re.I),
    re.compile(r"\b(ultrassonografia|ultrassom|ultrasound)\b", re.I),
    re.compile(r"\b(radiografia|radio\s*grafia)\b", re.I),
    re.compile(r"\b(laboratório|laboratorio|exames?\s+de\s+sangue)\b", re.I),
    re.compile(r"\b(eletrocardiograma|ecg)\b", re.I),
    re.compile(r"\b(ressonância\s+magnética|ressonancia)\b", re.I),
    re.compile(r"\b(tomografia)\b", re.I),
    re.compile(r"\b(biópsia)\b", re.I),
    re.compile(r"\b(colonoscopia)\b", re.I),
    re.compile(r"\b(endoscopia)\b", re.I),
    re.compile(r"\b(vacina|vacinação|vaccine)\b", re.I),
    re.compile(r"\b(fisioterapia)\b", re.I),
    re.compile(r"\b(terapia\s+ocupacional)\b", re.I),
    re.compile(r"\b(psychotherapy|sessão|sessao|atendimento\s+psicológico)\b", re.I),
]

# Date reference patterns
_DATE_PATTERNS = [
    re.compile(r"\b(amanhã|depois\s+de\s+amanhã|hoje|agora)\b", re.I),
    re.compile(r"\b(dia\s+\d{1,2})\b", re.I),
    re.compile(r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b", re.I),
    re.compile(r"\b(próxima?\s+(?:semana|segunda|terça|quarta|quinta|sexta|sábado|domingo))\b", re.I),
    re.compile(r"\b(segunda-feira|terça-feira|quarta-feira|quinta-feira|sexta-feira|sábado|domingo)\b", re.I),
]

# Time period patterns
_TIME_PATTERNS = [
    re.compile(r"\b(manhã|tarde|noite)\b", re.I),
    re.compile(r"\b(\d{1,2}:\d{2})\b", re.I),
    re.compile(r"\b(meio-dia|meio dia|meio-da-tarde)\b", re.I),
    re.compile(r"\b(ao\s+(?:manhã|tarde|noite))\b", re.I),
    re.compile(r"\b(durante\s+o\s+(?:dia|expediente))\b", re.I),
]

# Clinic info topic patterns
_CLINIC_INFO_PATTERNS = [
    re.compile(r"\b(endereço|endereco|rua|av\.|avenida)\b", re.I),
    re.compile(r"\b(telefone|tel|contato)\b", re.I),
    re.compile(r"\b(funcionamento|abertura)\b", re.I),
    re.compile(r"\b(local|localização|localizacao|onde\s+fica|onde\s+esta|onde\s+vcs|onde\s+vocês)\b", re.I),
    re.compile(r"\b(preço|preco|valor|quanto\s+custa|custo)\b", re.I),
    re.compile(r"\b(convênio|convenio|plano\s+de\s+saúde)\b", re.I),
    re.compile(r"\b(emergência|urgência|pronto\s+socorro)\b", re.I),
    re.compile(r"\b(estacionamento)\b", re.I),
    re.compile(r"\b(wi-?fi|internet)\b", re.I),
    re.compile(r"\b(nome\s+da\s+clínica)\b", re.I),
    re.compile(r"\b(nome\s+da\s+clnica)\b", re.I),
    re.compile(r"\bclínica\b", re.I),
    re.compile(r"\bclnica\b", re.I),
    re.compile(r"\b(atendem|atendimento|atende)\b", re.I),
    re.compile(r"\b(sábado|sábados|sabado|domingo|feriado)\b", re.I),
]

# Map entity type to its patterns
_ENTITY_PATTERN_MAP = {
    "greeting": _GREETING_PATTERNS,
    "professional_name": _PROFESSIONAL_PATTERNS,
    "specialty": _SPECIALTY_PATTERNS,
    "insurance_plan": _INSURANCE_PATTERNS,
    "service_name": _SERVICE_PATTERNS,
    "date_reference": _DATE_PATTERNS,
    "time_period": _TIME_PATTERNS,
    "clinic_info_topic": _CLINIC_INFO_PATTERNS,
}

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class DetectedEntities:
    """Result of NER detection."""

    professional_name: Optional[str] = None
    specialty: Optional[str] = None
    insurance_plan: Optional[str] = None
    service_name: Optional[str] = None
    date_reference: Optional[str] = None
    time_period: Optional[str] = None
    clinic_info_topic: Optional[str] = None
    greeting: bool = False

    # Metadata
    raw_gliner_results: list = field(default_factory=list)
    gliner_used: bool = False
    entity_count: int = 0
    confidence_map: dict = field(default_factory=dict)

    def __post_init__(self):
        self.entity_count = sum(
            1 for v in [
                self.professional_name,
                self.specialty,
                self.insurance_plan,
                self.service_name,
                self.date_reference,
                self.time_period,
                self.clinic_info_topic,
            ]
            if v is not None
        ) + (1 if self.greeting else 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_specialty(raw: str) -> str:
    """Normalize specialty name to canonical form."""
    raw_lower = raw.lower().strip()

    mapping = {
        "clínico geral": "Clínico Geral",
        "clinico geral": "Clínico Geral",
        "clínica geral": "Clínico Geral",
        "pediatria": "Pediatria",
        "pediatra": "Pediatria",
        "ginecologia": "Ginecologia",
        "ginecologista": "Ginecologia",
        "obstetrícia": "Obstetrícia",
        "obstetra": "Obstetrícia",
        "dermatologia": "Dermatologia",
        "dermatologista": "Dermatologia",
        "cardiologia": "Cardiologia",
        "cardiologista": "Cardiologia",
        "neurologia": "Neurologia",
        "neurologista": "Neurologia",
        "ortopedia": "Ortopedia",
        "ortopedista": "Ortopedia",
        "traumatologia": "Ortopedia",
        "oftalmologia": "Oftalmologia",
        "oftalmologista": "Oftalmologia",
        "psicologia": "Psicologia",
        "psicólogo": "Psicologia",
        "psicóloga": "Psicologia",
        "psiquiatria": "Psiquiatria",
        "psiquiatra": "Psiquiatria",
        "endocrinologia": "Endocrinologia",
        "endocrinologista": "Endocrinologia",
        "gastroenterologia": "Gastroenterologia",
        "gastroenterologista": "Gastroenterologia",
        "urologia": "Urologia",
        "urologista": "Urologia",
        "geriatria": "Geriatria",
        "geriatra": "Geriatria",
        "pneumologia": "Pneumologia",
        "pneumologista": "Pneumologia",
        "reumatologia": "Reumatologia",
        "reumatologista": "Reumatologia",
        "alergologia": "Alergologia",
        "alergista": "Alergologia",
        "imunologia": "Alergologia",
        "imunologista": "Alergologia",
        "oncologia": "Oncologia",
        "oncologista": "Oncologia",
        "cirurgia": "Cirurgia",
        "cirurgião": "Cirurgia",
        "cirurgiã": "Cirurgia",
        "radiologia": "Radiologia",
        "radiologista": "Radiologia",
        "anestesiologia": "Anestesiologia",
        "anestesiologista": "Anestesiologia",
        "medicina do trabalho": "Medicina do Trabalho",
        "estética médica": "Estética Médica",
        "nutrologia": "Nutrologia",
        "nutrologista": "Nutrologia",
        "geral": "Clínico Geral",
    }

    # Direct match
    if raw_lower in mapping:
        return mapping[raw_lower]

    # Partial match for multi-word
    for key, value in mapping.items():
        if key in raw_lower or raw_lower in key:
            return value

    # Title-case fallback
    return raw.strip().title()


# ---------------------------------------------------------------------------
# NerService
# ---------------------------------------------------------------------------

class NerService:
    """
    NER service that wraps GLiNER for entity extraction.

    Tries to load GLiNER (urchade/gliner-multilingual-v2.5). Falls back to
    regex-based greedy detection if GLiNER is unavailable or fails to load.
    """

    _instance: Optional["NerService"] = None
    _gliner_model: Optional[object] = None
    _gliner_available: bool = False

    def __new__(cls) -> "NerService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._gliner_model = None
            cls._gliner_available = False
            cls._instance._load_model()
        return cls._instance

    def _load_model(self) -> None:
        """Try to load GLiNER model. Silently falls back if unavailable."""
        try:
            from gliner import GLiNER

            self._gliner_model = GLiNER.from_pretrained("urchade/gliner-multilingual-v2.5")
            self._gliner_available = True
        except Exception:
            self._gliner_model = None
            self._gliner_available = False

    def detect(self, text: str) -> DetectedEntities:
        """
        Detect entities in the given text.

        Uses GLiNER if available, otherwise falls back to greedy regex detection.
        """
        if self._gliner_available and self._gliner_model is not None:
            return self._detect_gliner(text)
        return self._detect_greedy(text)

    def _detect_gliner(self, text: str) -> DetectedEntities:
        """Detect entities using GLiNER model."""
        try:
            entities = self._gliner_model.predict_entities(text, _ENTITY_LABELS, threshold=0.3)

            result = DetectedEntities(raw_gliner_results=entities, gliner_used=True)
            confidence_map: dict = {}

            for entity in entities:
                label = entity.get("label", "")
                text_found = entity.get("text", "")
                score = entity.get("score", 0.0)

                if label == "professional_name":
                    result.professional_name = text_found
                elif label == "specialty":
                    result.specialty = _normalize_specialty(text_found)
                elif label == "insurance_plan":
                    result.insurance_plan = text_found
                elif label == "service_name":
                    result.service_name = text_found
                elif label == "date_reference":
                    result.date_reference = text_found
                elif label == "time_period":
                    result.time_period = text_found
                elif label == "clinic_info_topic":
                    result.clinic_info_topic = text_found
                elif label == "greeting":
                    result.greeting = True

                confidence_map[label] = score

            result.confidence_map = confidence_map
            return result

        except Exception:
            # GLiNER failed at runtime — fall back to greedy
            return self._detect_greedy(text)

    def _detect_greedy(self, text: str) -> DetectedEntities:
        """
        Greedy regex-based entity detection (fallback when GLiNER unavailable).

        Scans patterns in priority order: greeting → professional_name → specialty
        → insurance_plan → service_name → date_reference → time_period →
        clinic_info_topic.
        """
        result = DetectedEntities(gliner_used=False)
        text_lower = text.lower()
        seen_labels: set = set()

        # Priority order for greedy detection
        priority_labels = [
            "greeting",
            "professional_name",
            "specialty",
            "insurance_plan",
            "service_name",
            "date_reference",
            "time_period",
            "clinic_info_topic",
        ]

        for label in priority_labels:
            if label in seen_labels:
                continue

            patterns = _ENTITY_PATTERN_MAP.get(label, [])
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    if label == "greeting":
                        result.greeting = True
                    elif label == "professional_name":
                        # Dr. Carlos → "Carlos"
                        if match.lastindex and match.lastindex >= 1:
                            captured = match.group(1).strip()
                            # If captured name is a title-only word (Dr, Dra, Médico),
                            # it's not a real name — skip this match and retry specialty
                            _TITLE_WORDS = frozenset({
                                "dr", "dra", "dra", "dr.", "dra.",
                                "médico", "médica", "medico", "medica",
                                "professor", "professora",
                            })
                            if captured.lower() in _TITLE_WORDS:
                                # Not a real name — skip professional_name, continue to specialty
                                continue
                            result.professional_name = captured
                        else:
                            name = match.group(0).strip()
                            # If entire match is just a title word, skip
                            _TITLE_ONLY = frozenset({"dr", "dra", "médico", "médica", "medico", "medica"})
                            if name.lower().rstrip(".") in _TITLE_ONLY:
                                continue
                            result.professional_name = name
                    elif label == "specialty":
                        result.specialty = _normalize_specialty(match.group(0))
                    elif label == "insurance_plan":
                        result.insurance_plan = match.group(1).strip() if match.lastindex else match.group(0).strip()
                    elif label == "service_name":
                        result.service_name = match.group(0).strip()
                    elif label == "date_reference":
                        result.date_reference = match.group(0).strip()
                    elif label == "time_period":
                        result.time_period = match.group(0).strip()
                    elif label == "clinic_info_topic":
                        result.clinic_info_topic = match.group(1).strip() if match.lastindex else match.group(0).strip()

                    seen_labels.add(label)
                    break

        return result
