"""Evaluation runner for repeated workflow executions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from briefsmith.llm import LLMClient
from briefsmith.runs import RunMetadata, RunStore
from briefsmith.schemas import (
    BriefInput,
    BriefOutput,
    BriefSections,
    ResearchFindings,
    SourceItem,
    WorkflowState,
    to_markdown,
)
from briefsmith.tools import WebSearchClient
from briefsmith.tools.cache import SearchCache
from briefsmith.workflows import build_graph, build_graph_no_research

from .metrics import brief_length_stats, count_citations_in_markdown, score_completeness


class CacheOnlySearchClient:
    """Search client wrapper that serves strictly from SearchCache."""

    def __init__(self, cache: SearchCache) -> None:
        self._cache = cache

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        q = query.strip()
        cached = self._cache.get(q)
        if cached is None:
            raise RuntimeError(
                "Offline mode cache miss for query "
                f"{q!r}. Run once without --offline to populate the search cache."
            )
        return cached[:max_results]


def _maybe_wrap_offline(search: WebSearchClient, offline: bool) -> WebSearchClient:
    """If offline, wrap DuckDuckGoSearchClient to enforce cache-only behavior."""
    if not offline:
        return search

    # DuckDuckGoSearchClient stores cache in a private attribute _cache.
    cache = getattr(search, "_cache", None)
    if cache is None:
        raise RuntimeError(
            "Offline mode requires DuckDuckGoSearchClient with a configured cache."
        )
    if not isinstance(cache, SearchCache):
        raise RuntimeError("Offline mode requires a SearchCache-backed search client.")

    return CacheOnlySearchClient(cache)


@dataclass(frozen=True)
class EvalRunner:
    llm: LLMClient
    search: WebSearchClient
    run_store: RunStore
    sources_override: list[SourceItem] | None = None

    def run_once(self, input: BriefInput, offline: bool = False) -> dict[str, Any]:
        """Run the workflow once and return metrics and metadata."""
        run_id: str | None = None
        started = perf_counter()
        try:
            run_id = self.run_store.create_run(input)

            if self.sources_override is not None:
                graph = build_graph_no_research(self.llm)
                initial = WorkflowState(
                    input=input,
                    plan=None,
                    sources=list(self.sources_override),
                    findings=None,
                    brief=None,
                    approval_status="pending",
                    revision_notes=None,
                    metadata={"revision_count": 0},
                )
            else:
                search_client = _maybe_wrap_offline(self.search, offline=offline)
                graph = build_graph(self.llm, search_client)
                initial = WorkflowState(
                    input=input,
                    plan=None,
                    sources=[],
                    findings=None,
                    brief=None,
                    approval_status="pending",
                    revision_notes=None,
                    metadata={"revision_count": 0},
                )
            final = graph.invoke(initial.model_dump(mode="json"))
            if not isinstance(final, dict):
                raise RuntimeError("Graph returned non-dict state")

            sources_raw = final.get("sources") or []
            self.run_store.save_json(run_id, "sources.json", sources_raw)
            sources = [SourceItem.model_validate(s) for s in sources_raw]

            findings_raw = final.get("findings")
            if findings_raw is None:
                raise RuntimeError("Missing findings in final state")
            self.run_store.save_json(run_id, "findings.json", findings_raw)
            findings = ResearchFindings.model_validate(findings_raw)

            brief_raw = final.get("brief")
            if brief_raw is None:
                raise RuntimeError("Missing brief in final state")
            self.run_store.save_json(run_id, "brief.json", brief_raw)
            brief = BriefSections.model_validate(brief_raw)

            output = BriefOutput(
                input=input,
                findings=findings,
                brief=brief,
                sources=sources,
                metadata=final.get("metadata") or {},
            )
            md = to_markdown(output)
            self.run_store.save_artifact(run_id, "final_brief.md", md.encode("utf-8"), "text/markdown")

            meta = final.get("metadata") or {}
            approval_status = str(final.get("approval_status", "pending"))
            revision_count = int(meta.get("revision_count", 0))

            completeness = score_completeness(output)
            citations = count_citations_in_markdown(md)
            brief_counts = brief_length_stats(brief)

            durations_ms = meta.get("durations_ms") or {}
            duration_ms: int | None = None
            if isinstance(durations_ms, dict) and durations_ms:
                try:
                    duration_ms = int(sum(int(v) for v in durations_ms.values()))
                except Exception:
                    duration_ms = None
            if duration_ms is None:
                duration_ms = int((perf_counter() - started) * 1000)

            run_metadata = RunMetadata(
                run_id=run_id,
                created_at=datetime.now(UTC),
                approval_status=approval_status,
                revision_count=revision_count,
                ollama_model=str(meta.get("writer_model", "ollama")),
                search_provider="duckduckgo",
                durations_ms=durations_ms if isinstance(durations_ms, dict) else {},
                notes=final.get("revision_notes"),
            )
            self.run_store.save_json(run_id, "run_metadata.json", run_metadata)

            return {
                "run_id": run_id,
                "approval_status": approval_status,
                "revision_count": revision_count,
                "citations": citations,
                "brief_counts": brief_counts,
                "hard_issues_count": completeness["hard_issues_count"],
                "soft_issues_count": completeness["soft_issues_count"],
                "issues": completeness["issues"],
                "duration_ms": duration_ms,
                "error": None,
            }
        except Exception as e:
            return {
                "run_id": run_id,
                "approval_status": None,
                "revision_count": None,
                "citations": None,
                "brief_counts": None,
                "hard_issues_count": None,
                "soft_issues_count": None,
                "issues": None,
                "duration_ms": int((perf_counter() - started) * 1000),
                "error": str(e),
            }

    def run_many(
        self, input: BriefInput, runs: int, offline: bool = False
    ) -> list[dict[str, Any]]:
        """Run the workflow multiple times; return list of per-run results."""
        if runs <= 0:
            return []
        results: list[dict[str, Any]] = []
        for _ in range(runs):
            results.append(self.run_once(input, offline=offline))
        return results

