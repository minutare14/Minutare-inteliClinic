"""Clinic-specific prompt additions.

These prompts are loaded at deploy startup and injected into the
core AI engine's system prompt as additional context.

The prompts defined here do NOT replace core safety or medical ethics prompts.
They ADD clinic-specific context: specialties, tone, local rules.

To customize for a new clinic:
    1. Create a ClinicPrompts instance in your clinic configuration
    2. Or load from a YAML/TOML file in clinic/prompts/

Example (clinic/prompts/prompts.yaml):
    specialty_context: |
        Esta clínica é especializada em ortopedia e fisioterapia.
        Os principais médicos são: Dr. Silva (ortopedia), Dra. Lima (fisio).
    tone: formal
    additional_rules:
        - Sempre mencionar que a clínica aceita Unimed e Bradesco Saúde.
        - Para dúvidas sobre exames, encaminhar para recepção.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClinicPrompts:
    """Complementary prompts for this clinic deploy.

    Injected into system prompts by the AI engine at runtime.
    All fields are optional — use only what's relevant for each clinic.
    """

    # Context about the clinic's medical specialties
    specialty_context: str = ""

    # Tone: "formal" | "friendly" | "professional"
    tone: str = "professional"

    # Additional operational rules in plain language
    additional_rules: list[str] = field(default_factory=list)

    # Insurance-specific guidance
    insurance_notes: str = ""

    # Anything the chatbot should proactively mention
    proactive_info: str = ""

    def build_system_addendum(self) -> str:
        """Build the system prompt addendum for this clinic.

        Returns a string to append to the core system prompt.
        Returns empty string if no customizations are configured.
        """
        parts: list[str] = []

        if self.specialty_context:
            parts.append(f"Especialidades e contexto clínico:\n{self.specialty_context}")

        if self.insurance_notes:
            parts.append(f"Convênios e planos:\n{self.insurance_notes}")

        if self.additional_rules:
            rules_text = "\n".join(f"- {r}" for r in self.additional_rules)
            parts.append(f"Regras operacionais adicionais:\n{rules_text}")

        if self.proactive_info:
            parts.append(f"Informações a mencionar proativamente:\n{self.proactive_info}")

        if self.tone == "formal":
            parts.append("Tom de comunicação: formal, use 'o(a) senhor(a)'.")
        elif self.tone == "friendly":
            parts.append("Tom de comunicação: amigável e acolhedor, use 'você'.")

        if not parts:
            return ""

        header = "--- Configurações específicas desta clínica ---"
        footer = "--- Fim das configurações específicas ---"
        return f"\n{header}\n" + "\n\n".join(parts) + f"\n{footer}\n"

    @classmethod
    def from_yaml(cls, path: str) -> "ClinicPrompts":
        """Load prompts from a YAML file in clinic/prompts/."""
        import yaml
        from pathlib import Path

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(
            specialty_context=data.get("specialty_context", ""),
            tone=data.get("tone", "professional"),
            additional_rules=data.get("additional_rules", []),
            insurance_notes=data.get("insurance_notes", ""),
            proactive_info=data.get("proactive_info", ""),
        )

    @classmethod
    def empty(cls) -> "ClinicPrompts":
        """Return an empty ClinicPrompts (no customizations)."""
        return cls()
