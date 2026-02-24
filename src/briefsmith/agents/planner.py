"""Planner agent: produces a step-by-step plan from BriefInput."""

from datetime import UTC, datetime

from pydantic import BaseModel, field_validator

from briefsmith.llm import LLMClient, generate_structured
from briefsmith.schemas import WorkflowState


class PlanOutput(BaseModel):
    """Structured plan: at least 5 steps to guide research and synthesis."""

    plan: list[str]

    @field_validator("plan")
    @classmethod
    def at_least_five(cls, v: list[str]) -> list[str]:
        if len(v) < 5:
            raise ValueError("plan must have at least 5 items")
        return v


PLANNER_SYSTEM = (
    "You are a senior marketing strategist and workflow planner. "
    "Produce a clear, ordered list of steps that will guide research and "
    "later synthesis of a marketing brief. Steps should be actionable."
)


def planner_agent(state: WorkflowState, llm: LLMClient) -> WorkflowState:
    """Produce a plan from BriefInput and store it in state with metadata."""
    inp = state.input
    prompt = (
        f"Product: {inp.product_name}\n"
        f"Description: {inp.product_description}\n"
        f"Target audience: {inp.target_audience}\n"
        f"Region: {inp.region}. Tone: {inp.tone}.\n"
        "Produce a step-by-step plan (at least 5 steps) for researching and "
        "synthesizing a marketing brief."
    )
    out = generate_structured(
        llm,
        system=PLANNER_SYSTEM,
        prompt=prompt,
        model=PlanOutput,
        max_retries=2,
    )
    return state.model_copy(
        update={
            "plan": out.plan,
            "metadata": {
                **state.metadata,
                "planner_completed_at": datetime.now(UTC).isoformat(),
            },
        }
    )
