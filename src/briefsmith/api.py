"""FastAPI web API for Briefsmith with run registry endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from briefsmith.llm import OllamaClient
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
from briefsmith.tools import DuckDuckGoSearchClient, SearchCache
from briefsmith.workflows import build_graph

app = FastAPI(
    title="Briefsmith API",
    description="Multi-agent workflow automator API",
    version="0.1.0",
)

run_store = RunStore()

ALLOWED_ARTIFACTS: set[str] = {
    "final_brief.md",
    "sources.json",
    "findings.json",
    "brief.json",
    "input.json",
    "run_metadata.json",
}


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


def _run_workflow(brief_input: BriefInput) -> dict[str, Any]:
    """Execute the workflow synchronously and return the final state dict."""
    llm = OllamaClient()
    cache = SearchCache()
    search = DuckDuckGoSearchClient(cache=cache)
    graph = build_graph(llm, search)

    initial = WorkflowState(
        input=brief_input,
        plan=None,
        sources=[],
        findings=None,
        brief=None,
        approval_status="pending",
        revision_notes=None,
        metadata={"revision_count": 0},
    )
    state_dict = initial.model_dump(mode="json")
    final = graph.invoke(state_dict)
    if not isinstance(final, dict):
        raise RuntimeError("Graph returned non-dict state")
    return final


def _persist_run(brief_input: BriefInput, final: dict[str, Any]) -> RunMetadata:
    """Persist artifacts for a finished run and return its metadata."""
    run_id = run_store.create_run(brief_input)

    sources = final.get("sources") or []
    run_store.save_json(run_id, "sources.json", sources)

    findings_data = final.get("findings")
    findings_model: ResearchFindings | None = None
    if findings_data is not None:
        run_store.save_json(run_id, "findings.json", findings_data)
        findings_model = ResearchFindings.model_validate(findings_data)

    brief_data = final.get("brief")
    brief_model: BriefSections | None = None
    if brief_data is not None:
        run_store.save_json(run_id, "brief.json", brief_data)
        brief_model = BriefSections.model_validate(brief_data)

    if brief_model is not None and findings_model is not None and sources:
        source_items = [SourceItem.model_validate(s) for s in sources]
        output = BriefOutput(
            input=brief_input,
            findings=findings_model,
            brief=brief_model,
            sources=source_items,
            metadata=final.get("metadata") or {},
        )
        final_md = to_markdown(output)
        run_store.save_artifact(
            run_id, "final_brief.md", final_md.encode("utf-8"), "text/markdown"
        )

    meta = final.get("metadata") or {}
    approval_status = final.get("approval_status", "pending")
    run_metadata = RunMetadata(
        run_id=run_id,
        created_at=datetime.now(UTC),
        approval_status=str(approval_status),
        revision_count=int(meta.get("revision_count", 0)),
        ollama_model=str(meta.get("writer_model", "ollama")),
        search_provider="duckduckgo",
        durations_ms=meta.get("durations_ms") or {},
        notes=final.get("revision_notes"),
    )
    run_store.save_json(run_id, "run_metadata.json", run_metadata)

    return run_metadata


@app.post("/run")
def create_run(brief_input: BriefInput) -> dict[str, Any]:
    """Run the workflow synchronously and register a new run."""
    final = _run_workflow(brief_input)
    run_metadata = _persist_run(brief_input, final)

    artifacts = sorted(ALLOWED_ARTIFACTS)
    return {
        "run_id": run_metadata.run_id,
        "approval_status": run_metadata.approval_status,
        "revision_count": run_metadata.revision_count,
        "artifacts": artifacts,
    }


@app.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=100)) -> list[RunMetadata]:
    """Return list of recent runs' metadata."""
    return run_store.list_runs(limit=limit)


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> RunMetadata:
    """Return metadata for a specific run."""
    try:
        return run_store.load_metadata(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/runs/{run_id}/artifact/{name}")
def get_artifact(run_id: str, name: str) -> FileResponse:
    """Return a specific artifact file for a run."""
    if name not in ALLOWED_ARTIFACTS:
        raise HTTPException(status_code=404, detail="Artifact not found")

    path = run_store.path_for(run_id, name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    media_type = "application/octet-stream"
    if name.endswith(".json"):
        media_type = "application/json"
    elif name.endswith(".md"):
        media_type = "text/markdown"

    return FileResponse(path, media_type=media_type)
