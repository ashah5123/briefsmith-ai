"""LangGraph workflow state schema."""

from typing import Any, Literal

from pydantic import BaseModel

from briefsmith.schemas.brief import BriefSections
from briefsmith.schemas.input import BriefInput
from briefsmith.schemas.research import ResearchFindings
from briefsmith.schemas.sources import SourceItem

ApprovalStatus = Literal["pending", "revise", "approved"]


class WorkflowState(BaseModel):
    """LangGraph state object. Kept stable and serializable for checkpointing."""

    input: BriefInput
    plan: list[str] | None = None
    sources: list[SourceItem] = []
    findings: ResearchFindings | None = None
    brief: BriefSections | None = None
    approval_status: ApprovalStatus = "pending"
    revision_notes: str | None = None
    metadata: dict[str, Any] = {}

    def with_metadata(self, key: str, value: Any) -> "WorkflowState":
        """Return a copy of this state with metadata updated for the given key."""
        new_metadata = dict(self.metadata)
        new_metadata[key] = value
        return self.model_copy(update={"metadata": new_metadata})
