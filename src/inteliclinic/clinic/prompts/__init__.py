"""Per-clinic prompt customizations.

Core system prompts live in core/ai_engine/.
These are COMPLEMENTARY prompts appended at deploy time.

Examples of what goes here:
- Clinic-specific tone and persona
- Additional context about the clinic's specialties
- Insurance-specific instructions
- Local operational rules in natural language

What does NOT go here:
- Core safety instructions (→ core/safety/policies/)
- Agent routing logic (→ core/ai_engine/nodes/)
- Response templates (→ core/ai_engine/nodes/fallback.py)
"""

from .base_prompts import ClinicPrompts

__all__ = ["ClinicPrompts"]
