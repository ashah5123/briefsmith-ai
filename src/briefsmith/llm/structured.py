"""Structured JSON extraction and generation with Pydantic."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from briefsmith.llm.client import LLMClient
from briefsmith.llm.errors import StructuredOutputError

T = TypeVar("T", bound=BaseModel)

SCHEMA_LIKE_KEYS = frozenset({"properties", "$schema", "title", "type"})


def _model_field_names(model: type[BaseModel]) -> list[str]:
    """Return the list of field names for the model."""
    return list(model.model_fields.keys())


def _example_instance_json(model: type[BaseModel]) -> str:
    """Build example JSON shape (field names + placeholders) for the model."""
    placeholders: dict[str, Any] = {}
    for name in model.model_fields:
        info = model.model_fields[name]
        ann = str(info.annotation)
        placeholders[name] = ["..."] if "list" in ann else "..."
    return json.dumps(placeholders, indent=2)


def _is_schema_like(obj: dict[str, Any], expected_fields: list[str]) -> bool:
    """True if obj looks like a JSON schema rather than an instance."""
    keys = set(obj.keys())
    has_schema_key = bool(keys & SCHEMA_LIKE_KEYS)
    has_expected = bool(keys & set(expected_fields))
    return bool(has_schema_key and not has_expected)


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


def _build_structured_prompt(
    prompt: str, model: type[BaseModel]
) -> str:
    """Build prompt with strict instructions and example instance shape."""
    instructions = (
        "Strict instructions:\n"
        "- Return ONLY a JSON object that matches the schema.\n"
        "- Do NOT return the schema itself.\n"
        "- No markdown, no commentary, no code fences.\n"
        "- All fields must be present."
    )
    example = _example_instance_json(model)
    example_label = "Example shape (use your own values):"
    return f"{prompt}\n\n{instructions}\n\n{example_label}\n{example}"


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
    expected_fields = _model_field_names(model)
    last_raw = ""
    last_extracted: str | None = None
    last_error: str | None = None
    current_prompt = _build_structured_prompt(prompt, model)

    for attempt in range(max_retries + 1):
        raw = client.generate_json(
            current_prompt,
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
                current_prompt = (
                    f"{current_prompt}\n\n[Correction: previous output was not "
                    f"valid JSON. Error: {e}. Try again with a single valid JSON only.]"
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
            parsed: dict[str, Any] = _json.loads(extracted)
        except _json.JSONDecodeError:
            parsed = {}

        if _is_schema_like(parsed, expected_fields):
            last_error = "Model returned a schema instead of an instance."
            if attempt < max_retries:
                current_prompt = (
                    f"{current_prompt}\n\n[Correction: You output a schema. "
                    "Output ONLY an INSTANCE with the required fields: "
                    f"{', '.join(expected_fields)}.]"
                )
                continue
            raise StructuredOutputError(
                f"Model returned schema-like JSON after {max_retries + 1} attempt(s).",
                last_raw_output=last_raw,
                last_extracted_json=last_extracted,
                validation_error=last_error,
            )

        try:
            return model.model_validate_json(extracted)
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                current_prompt = (
                    f"{current_prompt}\n\n[Correction: validation failed. Error: {e}. "
                    f"Required keys: {', '.join(expected_fields)}. "
                    "Output must be a single JSON object with these fields.]"
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
