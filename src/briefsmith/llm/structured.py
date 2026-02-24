"""Structured JSON extraction and generation with Pydantic."""

import json
from typing import TypeVar

from pydantic import BaseModel

from briefsmith.llm.client import LLMClient
from briefsmith.llm.errors import StructuredOutputError

T = TypeVar("T", bound=BaseModel)


def extract_first_json_object(text: str) -> str:
    """Find the first valid JSON object in text (e.g. model output with markdown)."""
    idx = 0
    while True:
        start = text.find("{", idx)
        if start == -1:
            raise ValueError("No '{' found in text; cannot extract JSON object")
        depth = 0
        in_string = False
        escape = False
        quote_char = '"'
        i = start
        while i < len(text):
            c = text[i]
            if escape:
                escape = False
                i += 1
                continue
            if c == "\\" and in_string:
                escape = True
                i += 1
                continue
            if in_string:
                if c == quote_char:
                    in_string = False
                i += 1
                continue
            if c == '"' or c == "'":
                in_string = True
                quote_char = c
                i += 1
                continue
            if c == "{":
                depth += 1
                i += 1
                continue
            if c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        pass
                i += 1
                continue
            i += 1
        idx = start + 1


def generate_text(client: LLMClient, system: str, prompt: str) -> str:
    """Generate plain text using the given client."""
    return client.generate(prompt, system=system or None)


def generate_structured(
    client: LLMClient,
    system: str,
    prompt: str,
    model: type[BaseModel],
    max_retries: int = 2,
) -> BaseModel:
    """Generate and validate a Pydantic model from LLM JSON. Retries on failure."""
    import json as _json

    schema = model.model_json_schema()
    schema_json = _json.dumps(schema, indent=2)
    last_raw = ""
    last_extracted: str | None = None
    last_error: str | None = None

    for attempt in range(max_retries + 1):
        raw = client.generate_json(
            prompt,
            schema_json=schema_json,
            system=system or None,
        )
        last_raw = raw
        try:
            extracted = extract_first_json_object(raw)
        except ValueError as e:
            last_extracted = None
            last_error = str(e)
            if attempt < max_retries:
                prompt = (
                    f"{prompt}\n\n[Correction: previous output was not valid JSON. "
                    f"Error: {e}. Try again with a single valid JSON object only.]"
                )
                continue
            n = max_retries + 1
            raise StructuredOutputError(
                f"Could not extract JSON after {n} attempt(s). {e}",
                last_raw_output=last_raw,
                last_extracted_json=None,
                validation_error=last_error,
            ) from e

        last_extracted = extracted
        try:
            return model.model_validate_json(extracted)
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                prompt = (
                    f"{prompt}\n\n[Correction: validation failed. Error: {e}. "
                    "Output must be a single JSON object conforming to the schema.]"
                )
                continue
            n = max_retries + 1
            raise StructuredOutputError(
                f"Structured output validation failed after {n} attempt(s). {e}",
                last_raw_output=last_raw,
                last_extracted_json=last_extracted,
                validation_error=last_error,
            ) from e

    raise StructuredOutputError(
        "Structured generation failed (unexpected).",
        last_raw_output=last_raw,
        last_extracted_json=last_extracted,
        validation_error=last_error,
    )
