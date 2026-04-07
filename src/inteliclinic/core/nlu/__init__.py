"""NLU (Natural Language Understanding) module — Instructor-based structured extraction.

Uses the `instructor` library to wrap LLM clients (OpenAI, Anthropic, Gemini)
and extract typed Pydantic models from unstructured patient messages.

Key components:
- schemas/       : Pydantic models (ExtractedMessage, Intent, ConfidenceLevel)
- extractors/    : InstructorMessageExtractor — low-level LLM call wrapper
- pipelines/     : ExtractionPipeline — orchestrates extraction with retries and fallbacks

All extraction is performed in a medical clinic context (pt-BR).
The extractor is intentionally conservative: it never assumes medical intent
and prefers marking a message as ambiguous over extrapolating.
"""
