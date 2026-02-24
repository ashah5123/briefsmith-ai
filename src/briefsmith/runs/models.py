"""Pydantic models for run metadata and registry."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    """Summary metadata for a single workflow run."""

    run_id: str
    created_at: datetime
    approval_status: str
    revision_count: int
    ollama_model: str
    search_provider: str = "duckduckgo"
    durations_ms: Dict[str, int] = Field(default_factory=dict)
    notes: Optional[str] = None

