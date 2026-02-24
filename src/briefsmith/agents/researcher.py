"""Researcher agent: builds queries, runs search, merges and dedupes sources."""

from datetime import UTC, datetime

from briefsmith.schemas import BriefInput, SourceItem, WorkflowState
from briefsmith.tools import WebSearchClient, deduplicate_sources

MAX_SOURCES_KEEP = 12
QUERIES_MIN = 5
QUERIES_MAX = 8
RESULTS_PER_QUERY = 5


def researcher_agent(
    state: WorkflowState, search: WebSearchClient
) -> WorkflowState:
    """Build 5–8 queries from input and plan, search, merge/dedupe, keep ~12."""
    inp = state.input
    plan = state.plan or []

    queries = _build_queries(inp, plan)
    queries = queries[:QUERIES_MAX]
    if len(queries) < QUERIES_MIN:
        base = f"{inp.product_name} {inp.target_audience} marketing"
        while len(queries) < QUERIES_MIN:
            queries.append(f"{base} angle {len(queries) + 1}")

    all_sources: list[SourceItem] = []
    for q in queries:
        results = search.search(q, max_results=RESULTS_PER_QUERY)
        all_sources.extend(results)

    merged = deduplicate_sources(all_sources)
    sources = merged[:MAX_SOURCES_KEEP]

    return state.model_copy(
        update={
            "sources": sources,
            "metadata": {
                **state.metadata,
                "researcher_queries": queries,
                "researcher_queries_count": len(queries),
                "researcher_sources_count": len(sources),
                "researcher_completed_at": datetime.now(UTC).isoformat(),
            },
        }
    )


def _build_queries(inp: BriefInput, plan: list[str]) -> list[str]:
    """Build 5–8 search queries from BriefInput and plan steps."""
    product = inp.product_name
    audience = inp.target_audience
    region = inp.region
    competitors = inp.competitors or []

    queries = [
        f"{product} market {region}",
        f"{product} target audience {audience}",
        f"{product} positioning competitors",
    ]
    for step in plan[:3]:
        step_clean = step.strip()
        if step_clean and step_clean.lower() not in (
            q.lower() for q in queries
        ):
            queries.append(f"{product} {step_clean}")
    for c in competitors[:2]:
        if c.strip():
            queries.append(f"{c.strip()} vs {product}")

    return queries[:QUERIES_MAX]
