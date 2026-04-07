"""Message extractors powered by Instructor.

InstructorMessageExtractor is the primary extractor used by ExtractionPipeline.
It wraps an async LLM client with Instructor's type-safe response parsing,
enabling automatic Pydantic validation and configurable retry logic.
"""
