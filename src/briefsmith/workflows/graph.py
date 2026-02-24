"""LangGraph: planner -> ... -> critic (revision loop)."""

from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from briefsmith.agents import (
    critic_agent,
    planner_agent,
    researcher_agent,
    synthesizer_agent,
    writer_agent,
)
from briefsmith.llm import LLMClient
from briefsmith.schemas import WorkflowState
from briefsmith.tools import WebSearchClient


def _route_after_critic(state: dict) -> str:
    """If revise and revision_count < 2, send to writer; else end."""
    if state.get("approval_status") != "revise":
        return "__end__"
    meta = state.get("metadata") or {}
    if meta.get("revision_count", 0) >= 2:
        return "__end__"
    return "writer"


def build_graph(
    llm: LLMClient, search: WebSearchClient
) -> Any:
    """Build and return compiled graph with writer/critic and revision loop."""
    builder = StateGraph(dict)

    def plan_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        t0 = perf_counter()
        out = planner_agent(ws, llm)
        elapsed_ms = int((perf_counter() - t0) * 1000)
        meta = dict(out.metadata)
        durations = dict(meta.get("durations_ms", {}))
        durations["planner"] = durations.get("planner", 0) + elapsed_ms
        meta["durations_ms"] = durations
        out = out.model_copy(update={"metadata": meta})
        return out.model_dump(mode="json")

    def research_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        t0 = perf_counter()
        out = researcher_agent(ws, search)
        elapsed_ms = int((perf_counter() - t0) * 1000)
        meta = dict(out.metadata)
        durations = dict(meta.get("durations_ms", {}))
        durations["researcher"] = durations.get("researcher", 0) + elapsed_ms
        meta["durations_ms"] = durations
        out = out.model_copy(update={"metadata": meta})
        return out.model_dump(mode="json")

    def synthesize_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        t0 = perf_counter()
        out = synthesizer_agent(ws, llm)
        elapsed_ms = int((perf_counter() - t0) * 1000)
        meta = dict(out.metadata)
        durations = dict(meta.get("durations_ms", {}))
        durations["synthesizer"] = durations.get("synthesizer", 0) + elapsed_ms
        meta["durations_ms"] = durations
        out = out.model_copy(update={"metadata": meta})
        return out.model_dump(mode="json")

    def writer_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        t0 = perf_counter()
        out = writer_agent(ws, llm)
        elapsed_ms = int((perf_counter() - t0) * 1000)
        meta = dict(out.metadata)
        durations = dict(meta.get("durations_ms", {}))
        durations["writer"] = durations.get("writer", 0) + elapsed_ms
        meta["durations_ms"] = durations
        out = out.model_copy(update={"metadata": meta})
        return out.model_dump(mode="json")

    def critic_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        t0 = perf_counter()
        out = critic_agent(ws, llm)
        elapsed_ms = int((perf_counter() - t0) * 1000)
        meta = dict(out.metadata)
        durations = dict(meta.get("durations_ms", {}))
        durations["critic"] = durations.get("critic", 0) + elapsed_ms
        meta["durations_ms"] = durations
        out = out.model_copy(update={"metadata": meta})
        return out.model_dump(mode="json")

    builder.add_node("planner", plan_node)
    builder.add_node("researcher", research_node)
    builder.add_node("synthesizer", synthesize_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "synthesizer")
    builder.add_edge("synthesizer", "writer")
    builder.add_edge("writer", "critic")
    builder.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"writer": "writer", "__end__": END},
    )

    return builder.compile()
