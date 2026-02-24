"""Final brief output schema."""

from typing import Any

from pydantic import BaseModel

from briefsmith.schemas.brief import BriefSections
from briefsmith.schemas.input import BriefInput
from briefsmith.schemas.research import ResearchFindings
from briefsmith.schemas.sources import SourceItem


class BriefOutput(BaseModel):
    """Complete brief output: input, findings, brief, sources, and optional metadata."""

    input: BriefInput
    findings: ResearchFindings
    brief: BriefSections
    sources: list[SourceItem]
    metadata: dict[str, Any] = {}
