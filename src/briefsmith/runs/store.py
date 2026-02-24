"""Filesystem-backed store for Briefsmith workflow runs."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, List

from briefsmith.schemas import BriefInput

from .models import RunMetadata


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write bytes to a file atomically (write to temp then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(content)
    tmp_path.replace(path)


class RunStore:
    """Simple run registry storing artifacts under base_dir/run_id/."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path("runs")

    # ----- ID / paths -------------------------------------------------

    def _generate_run_id(self) -> str:
        now = datetime.now(UTC)
        ts = now.strftime("%Y%m%d_%H%M%S")
        suffix = secrets.token_hex(3)
        return f"{ts}_{suffix}"

    def _run_dir(self, run_id: str) -> Path:
        return self.base_dir / run_id

    def path_for(self, run_id: str, filename: str) -> Path:
        """Return absolute path for an artifact within a run."""
        return self._run_dir(run_id) / filename

    # ----- CRUD -------------------------------------------------------

    def create_run(self, input: BriefInput) -> str:
        """Create a new run directory and persist the input JSON."""
        run_id = self._generate_run_id()
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=False)

        self.save_json(run_id, "input.json", input)
        return run_id

    def save_artifact(
        self,
        run_id: str,
        filename: str,
        content_bytes: bytes,
        content_type: str | None = None,
    ) -> None:
        """Save an arbitrary artifact as bytes (atomic write)."""
        # content_type is reserved for future use (e.g. setting metadata).
        path = self.path_for(run_id, filename)
        _atomic_write_bytes(path, content_bytes)

    def save_json(self, run_id: str, filename: str, obj: Any) -> None:
        """Encode an object as JSON and save atomically."""
        if hasattr(obj, "model_dump"):
            payload = obj.model_dump(mode="json")  # type: ignore[call-arg]
        else:
            payload = obj
        data = json.dumps(payload, indent=2, ensure_ascii=False)
        self.save_artifact(run_id, filename, data.encode("utf-8"), "application/json")

    def load_metadata(self, run_id: str) -> RunMetadata:
        """Load run_metadata.json for a given run_id."""
        path = self.path_for(run_id, "run_metadata.json")
        if not path.is_file():
            raise FileNotFoundError(f"run_metadata.json not found for run_id={run_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return RunMetadata.model_validate(raw)

    def list_runs(self, limit: int = 20) -> list[RunMetadata]:
        """Return latest runs up to limit, sorted by created_at desc."""
        if limit <= 0:
            return []

        runs: List[RunMetadata] = []
        if not self.base_dir.exists():
            return []

        # Iterate directories and collect any with valid metadata.
        for child in self.base_dir.iterdir():
            if not child.is_dir():
                continue
            meta_path = child / "run_metadata.json"
            if not meta_path.is_file():
                continue
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                meta = RunMetadata.model_validate(data)
            except Exception:
                continue
            runs.append(meta)

        runs.sort(key=lambda m: m.created_at, reverse=True)
        return runs[:limit]

    def load_json(self, run_id: str, filename: str) -> Any:
        """Load and parse a JSON artifact for a run."""
        path = self.path_for(run_id, filename)
        if not path.is_file():
            raise FileNotFoundError(f"{filename} not found for run_id={run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

