"""Source item and bundle schemas for research references."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class SourceItem(BaseModel):
    """A single research source (URL with optional title and snippet)."""

    url: str
    title: str | None = None
    snippet: str
    accessed_at: datetime = Field(default_factory=_utc_now)


class SourceBundle(BaseModel):
    """Wrapper for a list of SourceItems (helps with structured LLM outputs)."""

    items: list[SourceItem] = []
