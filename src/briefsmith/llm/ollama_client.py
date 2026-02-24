"""Ollama HTTP client for local LLM inference."""

import os
from typing import Any

import requests

OLLAMA_DEFAULT_BASE = "http://localhost:11434"
OLLAMA_GENERATE_PATH = "/api/generate"


def _env_int(key: str, default: int) -> int:
    """Parse env as int or return default."""
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


class OllamaClient:
    """HTTP client for Ollama local server. Implements LLMClient."""

    def __init__(
        self,
        base_url: str = OLLAMA_DEFAULT_BASE,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3")
        self.timeout = (
            timeout if timeout is not None else _env_int("OLLAMA_TIMEOUT", 120)
        )

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Call Ollama POST /api/generate with stream=false. Return raw text."""
        full_prompt = self._build_prompt(prompt, system)
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
        }
        url = f"{self.base_url}{OLLAMA_GENERATE_PATH}"
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(
                f"Ollama request failed: {e}. Is Ollama running at {self.base_url}?"
            ) from e
        data = resp.json()
        if "response" not in data:
            raise RuntimeError(f"Ollama returned unexpected body: {list(data.keys())}")
        return data["response"]

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        """Generate only valid JSON. Injects schema and strict JSON instruction."""
        json_rule = (
            "You must respond with ONLY a valid JSON object. "
            "No markdown, no explanation, no code fence. Raw JSON only."
        )
        schema_block = f"Schema (strict):\n{schema_json}"
        parts = [schema_block]
        if system and system.strip():
            parts.insert(0, system.strip())
        parts.insert(0, json_rule)
        combined_system = "\n\n".join(parts)
        wrapped_prompt = (
            f"{prompt}\n\nOutput a single JSON object that conforms to the schema."
        )
        return self.generate(wrapped_prompt, system=combined_system)

    def _build_prompt(self, prompt: str, system: str | None) -> str:
        """Prepend system message as header when provided."""
        if not system or not system.strip():
            return prompt
        return f"[System]\n{system.strip()}\n\n[User]\n{prompt}"
