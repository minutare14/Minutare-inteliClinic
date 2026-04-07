"""Clinic brand data object — assembled from ClinicSettings at startup."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClinicBrand:
    """Immutable brand descriptor for this clinic deploy."""

    clinic_name: str
    short_name: str
    chatbot_name: str
    greeting_template: str
    primary_color: str
    logo_path: str
    after_hours_message: str

    def get_greeting(self) -> str:
        return self.greeting_template.format(clinic_name=self.short_name)

    def get_system_signature(self) -> str:
        """One-line identity string injected into system prompts."""
        return f"Você é {self.chatbot_name}, assistente virtual da {self.clinic_name}."

    @classmethod
    def from_settings(cls, settings) -> "ClinicBrand":
        """Build ClinicBrand from a ClinicSettings instance."""
        return cls(
            clinic_name=settings.name,
            short_name=settings.short_name,
            chatbot_name=settings.chatbot_name,
            greeting_template=settings.chatbot_greeting,
            primary_color=settings.primary_color,
            logo_path=settings.logo_path,
            after_hours_message=settings.after_hours_message,
        )
