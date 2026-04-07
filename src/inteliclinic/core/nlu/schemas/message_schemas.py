"""Pydantic schemas for structured NLU extraction using Instructor.

These schemas define the typed output that InstructorMessageExtractor produces
from unstructured patient messages. All fields are designed to be safe for
a Brazilian medical clinic context: no diagnostic inference, no clinical advice.

Usage:
    extractor = InstructorMessageExtractor()
    result: ExtractedMessage = await extractor.extract("Quero marcar uma consulta")
    # result.intent == Intent.SCHEDULING
    # result.confidence == 0.92
    # result.desired_specialty == None  (patient didn't specify)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Intent(str, Enum):
    """Primary detected intents for clinic conversations."""

    SCHEDULING = "scheduling"
    """Patient wants to book a new appointment."""

    CANCEL = "cancel"
    """Patient wants to cancel an existing appointment."""

    RESCHEDULE = "reschedule"
    """Patient wants to move an existing appointment to a different time."""

    INSURANCE = "insurance"
    """Patient is asking about health insurance/convenio coverage or authorization."""

    FINANCIAL = "financial"
    """Patient is asking about prices, payment methods, or billing."""

    GLOSA = "glosa"
    """Internal: billing/glosa anomaly review (staff-initiated, not patient-facing)."""

    URGENT = "urgent"
    """Patient message indicates an urgent or emergency situation."""

    GREETING = "greeting"
    """Patient is greeting or starting a conversation without a specific request."""

    FAQ = "faq"
    """Patient has a general question (hours, location, preparation for exams, etc.)."""

    OTHER = "other"
    """Intent could not be classified into any of the above categories."""


class ConfidenceLevel(str, Enum):
    """Categorical confidence derived from the numeric confidence score.

    Used for routing decisions in the graph:
    - HIGH   : proceed normally
    - MEDIUM : proceed with optional confirmation step
    - LOW    : route to fallback or request clarification
    """

    HIGH = "high"
    """Confidence > 0.80 — extraction is reliable."""

    MEDIUM = "medium"
    """Confidence 0.60–0.80 — proceed but consider confirming with patient."""

    LOW = "low"
    """Confidence < 0.60 — trigger fallback or ask clarifying question."""


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert a numeric confidence score to a ConfidenceLevel enum value."""
    if confidence >= 0.80:
        return ConfidenceLevel.HIGH
    if confidence >= 0.60:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class ExtractedMessage(BaseModel):
    """Structured extraction from a patient message.

    Used by Instructor to transform unstructured text into typed, validated data.
    The model is intentionally conservative: fields are None by default and are
    only populated when the extractor has high confidence in the value.

    This model must NEVER contain:
    - Medical diagnoses or clinical recommendations
    - Assumptions about the patient's health condition
    - Extrapolated information not present in the message

    Example input:  "Boa tarde, preciso marcar uma consulta de cardiologia para minha mãe"
    Example output:
        intent=Intent.SCHEDULING
        confidence=0.91
        patient_name=None  (the patient mentioned "minha mãe", not themselves)
        desired_specialty="cardiologia"
        needs_clarification=True
        clarification_question="O agendamento é para você ou para outra pessoa?"
    """

    # ── Core classification ───────────────────────────────────────────────────
    intent: Intent = Field(
        ...,
        description="Primary detected intent of the patient message.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence score between 0 and 1 reflecting how certain the extraction is. "
            "Be conservative — prefer a lower score when the message is ambiguous."
        ),
    )
    confidence_level: ConfidenceLevel = Field(
        default=ConfidenceLevel.LOW,
        description="Categorical confidence level derived from the numeric score.",
    )

    # ── Patient identity ──────────────────────────────────────────────────────
    patient_name: str | None = Field(
        None,
        description=(
            "Patient's name if explicitly mentioned in the message. "
            "Do not infer from indirect references (e.g., 'minha mãe')."
        ),
    )

    # ── Scheduling fields ─────────────────────────────────────────────────────
    desired_specialty: str | None = Field(
        None,
        description=(
            "Medical specialty requested, as mentioned by the patient. "
            "Normalize to lowercase (e.g., 'cardiologia', 'ortopedia'). "
            "None if not specified."
        ),
    )
    desired_professional: str | None = Field(
        None,
        description=(
            "Doctor's name if the patient specified a preference. "
            "Preserve the name as mentioned. None if not specified."
        ),
    )
    desired_date: str | None = Field(
        None,
        description=(
            "Desired appointment date. Normalize to ISO 8601 (YYYY-MM-DD) when possible. "
            "Accept relative expressions like 'amanhã', 'próxima segunda' and normalize them. "
            "If normalization is impossible, preserve the original expression. None if not mentioned."
        ),
    )
    desired_time: str | None = Field(
        None,
        description=(
            "Desired appointment time (e.g., '14:00', 'manhã', 'tarde'). "
            "Normalize to HH:MM when an exact time is given. None if not mentioned."
        ),
    )

    # ── Insurance ─────────────────────────────────────────────────────────────
    insurance_plan: str | None = Field(
        None,
        description=(
            "Health insurance plan or convenio mentioned by the patient. "
            "Preserve the exact name as stated (e.g., 'Unimed', 'Bradesco Saúde'). "
            "None if not mentioned or if the patient indicates they are a private payer."
        ),
    )

    # ── Safety / Urgency ──────────────────────────────────────────────────────
    urgency_detected: bool = Field(
        False,
        description=(
            "True if the message contains signals of urgency or medical emergency. "
            "Err on the side of True when in doubt — false positives are safer than false negatives."
        ),
    )
    urgency_signals: list[str] = Field(
        default_factory=list,
        description=(
            "Specific phrases or words that triggered the urgency detection. "
            "Examples: ['dor forte no peito', 'falta de ar', 'urgente']."
        ),
    )

    # ── Ambiguity / Clarification ─────────────────────────────────────────────
    is_ambiguous: bool = Field(
        False,
        description=(
            "True if the intent or key information cannot be determined with confidence. "
            "When True, needs_clarification should also be True."
        ),
    )
    ambiguity_reason: str | None = Field(
        None,
        description="Brief explanation of why the message is ambiguous. None if not ambiguous.",
    )
    needs_clarification: bool = Field(
        False,
        description=(
            "True if additional information from the patient is required to proceed. "
            "Can be True even when the intent is clear (e.g., specialty not specified for scheduling)."
        ),
    )
    clarification_question: str | None = Field(
        None,
        description=(
            "The exact question to ask the patient in Brazilian Portuguese. "
            "Must be polite, concise, and ask for exactly one piece of information. "
            "None if needs_clarification is False."
        ),
    )

    # ── FAQ ───────────────────────────────────────────────────────────────────
    question_type: str | None = Field(
        None,
        description=(
            "Category of FAQ question when intent is Intent.FAQ. "
            "Examples: 'horario_funcionamento', 'localizacao', 'preparo_exame', "
            "'documentos_necessarios', 'estacionamento'. None for non-FAQ intents."
        ),
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    original_text: str = Field(
        ...,
        description="The original patient message, unmodified.",
    )
    language_detected: Literal["pt", "en", "es", "other"] = Field(
        "pt",
        description=(
            "Language detected in the message. "
            "The system is optimized for Brazilian Portuguese ('pt')."
        ),
    )

    @field_validator("confidence_level", mode="before")
    @classmethod
    def derive_confidence_level(cls, v: str | ConfidenceLevel) -> ConfidenceLevel:
        """Allow the LLM to return the string value; always validate against enum."""
        if isinstance(v, ConfidenceLevel):
            return v
        return ConfidenceLevel(v)

    @model_validator(mode="after")
    def sync_confidence_level(self) -> ExtractedMessage:
        """Ensure confidence_level always matches the numeric confidence field.

        This prevents the LLM from returning inconsistent combinations like
        confidence=0.3 with confidence_level='high'.
        """
        self.confidence_level = _confidence_to_level(self.confidence)
        return self

    @model_validator(mode="after")
    def validate_clarification_consistency(self) -> ExtractedMessage:
        """Ensure clarification fields are internally consistent."""
        if self.needs_clarification and not self.clarification_question:
            # Provide a safe default question when the LLM forgot to include one
            self.clarification_question = (
                "Poderia me fornecer mais detalhes para que eu possa te ajudar melhor?"
            )
        if self.is_ambiguous and not self.needs_clarification:
            self.needs_clarification = True
        return self

    @model_validator(mode="after")
    def validate_urgency_consistency(self) -> ExtractedMessage:
        """When urgency is detected, intent should be URGENT unless already set."""
        if self.urgency_detected and self.intent not in (Intent.URGENT, Intent.SCHEDULING):
            self.intent = Intent.URGENT
        return self

    def is_actionable(self) -> bool:
        """True if the extraction has enough information to proceed without clarification."""
        return (
            not self.needs_clarification
            and not self.is_ambiguous
            and self.confidence >= 0.60
        )

    def to_state_dict(self) -> dict:
        """Serialize to a dict suitable for storing in ClinicState.extracted_data."""
        return self.model_dump(mode="json")
