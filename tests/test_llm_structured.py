"""Tests for LLM structured output: extract_first_json_object, generate_structured."""

from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from briefsmith.llm import StructuredOutputError, generate_structured
from briefsmith.llm.structured import extract_first_json_object


class _TinyModel(BaseModel):
    """Minimal Pydantic model for tests."""

    answer: str = "ok"


def test_extract_first_json_object_plain() -> None:
    """Extract when text is only a JSON object."""
    text = '{"answer": "ok"}'
    assert extract_first_json_object(text) == text


def test_extract_first_json_object_with_markdown() -> None:
    """Extract when JSON is wrapped in markdown code fence."""
    text = 'Here is the result:\n```json\n{"answer": "yes"}\n```'
    assert extract_first_json_object(text) == '{"answer": "yes"}'


def test_extract_first_json_object_leading_junk() -> None:
    """Extract when there is leading text before the first object."""
    text = 'Sure. {"answer": "done"}'
    assert extract_first_json_object(text) == '{"answer": "done"}'


def test_extract_first_json_object_trailing_junk() -> None:
    """Extract when there is trailing text after the object."""
    text = '{"answer": "done"} Ignore this.'
    assert extract_first_json_object(text) == '{"answer": "done"}'


def test_extract_first_json_object_nested() -> None:
    """Extract object with nested object."""
    text = 'Prefix {"outer": {"inner": 1}} suffix'
    assert extract_first_json_object(text) == '{"outer": {"inner": 1}}'


def test_extract_first_json_object_skips_invalid_then_returns_valid() -> None:
    """First { ... } is invalid JSON; second is valid."""
    text = ' { invalid } then {"answer": "ok"}'
    assert extract_first_json_object(text) == '{"answer": "ok"}'


def test_extract_first_json_object_no_brace_raises() -> None:
    """Raise when no '{' is present."""
    with pytest.raises(ValueError, match="No '{' found"):
        extract_first_json_object("no json here")


def test_extract_first_json_object_unbalanced_raises() -> None:
    """Raise when no complete object (unbalanced braces)."""
    with pytest.raises(ValueError, match="No .*JSON"):
        extract_first_json_object(" {  ")


class FakeLLMClient:
    """Mock that returns invalid JSON first, then valid JSON."""

    def __init__(self, responses: list[str]) -> None:
        self._responses: Iterator[str] = iter(responses)

    def generate(self, prompt: str, system: str | None = None) -> str:
        return next(self._responses, "")

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        return next(self._responses, "")


def test_generate_structured_retries_then_succeeds() -> None:
    """First call invalid JSON, second valid; validate into Pydantic model."""
    client = FakeLLMClient(
        [
            "not valid json at all",
            '{"answer": "ok"}',
        ]
    )
    result = generate_structured(
        client,
        system="Test",
        prompt="Return answer ok",
        model=_TinyModel,
        max_retries=2,
    )
    assert isinstance(result, _TinyModel)
    assert result.answer == "ok"


def test_generate_structured_validation_retry_then_succeeds() -> None:
    """First JSON is invalid for model (wrong shape), second is valid."""
    client = FakeLLMClient(
        [
            '{"wrong": "field"}',
            '{"answer": "ok"}',
        ]
    )
    result = generate_structured(
        client,
        system="Test",
        prompt="Return JSON with 'answer' field.",
        model=_TinyModel,
        max_retries=2,
    )
    assert result.answer == "ok"


def test_generate_structured_fails_raises_structured_output_error() -> None:
    """When all retries return invalid JSON, raise StructuredOutputError."""
    client = FakeLLMClient(["still not json", "also not json", "nope"])
    with pytest.raises(StructuredOutputError) as exc_info:
        generate_structured(
            client,
            system="",
            prompt="Return JSON",
            model=_TinyModel,
            max_retries=2,
        )
    err = exc_info.value
    assert "last_raw_output" in dir(err)
    assert err.last_raw_output
    assert err.validation_error or err.last_extracted_json is None
