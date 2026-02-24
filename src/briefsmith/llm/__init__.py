"""LLM layer: Ollama client, structured JSON output, and utilities."""

from briefsmith.llm.client import LLMClient
from briefsmith.llm.errors import StructuredOutputError
from briefsmith.llm.ollama_client import OllamaClient
from briefsmith.llm.structured import generate_structured, generate_text

__all__ = [
    "LLMClient",
    "OllamaClient",
    "StructuredOutputError",
    "generate_structured",
    "generate_text",
]
