"""Minimal FastAPI web API for Briefsmith."""

from fastapi import FastAPI

app = FastAPI(
    title="Briefsmith API",
    description="Multi-agent workflow automator API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
