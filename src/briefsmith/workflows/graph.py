"""LangGraph workflow: planner -> researcher -> synthesizer."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from briefsmith.agents import planner_agent, researcher_agent, synthesizer_agent
from briefsmith.llm import LLMClient
from briefsmith.schemas import WorkflowState
from briefsmith.tools import WebSearchClient


def build_graph(
    llm: LLMClient, search: WebSearchClient
) -> Any:
    """Build and return compiled graph: planner -> researcher -> synthesizer."""
    builder = StateGraph(dict)

    def plan_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        out = planner_agent(ws, llm)
        return out.model_dump(mode="json")

    def research_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        out = researcher_agent(ws, search)
        return out.model_dump(mode="json")

    def synthesize_node(state: dict) -> dict:
        ws = WorkflowState.model_validate(state)
        out = synthesizer_agent(ws, llm)
        return out.model_dump(mode="json")

    builder.add_node("planner", plan_node)
    builder.add_node("researcher", research_node)
    builder.add_node("synthesizer", synthesize_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()
