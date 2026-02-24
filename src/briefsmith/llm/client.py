"""LLM client protocol: plain text and JSON generation."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients (Ollama, mocks, etc.)."""

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate plain text from a prompt and optional system message."""
        ...

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        """Generate only valid JSON matching the given schema. Returns raw text."""
        ...
