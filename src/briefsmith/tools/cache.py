"""File-based JSON cache for search results."""

import hashlib
import json
from pathlib import Path

from briefsmith.schemas import SourceItem

DEFAULT_CACHE_DIR = Path(".cache/briefsmith/search")


class SearchCache:
    """Simple file-based JSON cache for search results. Safe writes."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self._dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR

    def _path(self, query: str) -> Path:
        h = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
        return self._dir / f"{h}.json"

    def get(self, query: str) -> list[SourceItem] | None:
        """Return cached results for the query, or None if miss."""
        path = self._path(query)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, list):
            return None
        try:
            return [SourceItem.model_validate(item) for item in data]
        except Exception:
            return None

    def set(self, query: str, results: list[SourceItem]) -> None:
        """Store results for the query. Creates directory if needed. Safe write."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(query)
        data = [r.model_dump(mode="json") for r in results]
        raw = json.dumps(data, indent=2, ensure_ascii=False)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(raw, encoding="utf-8")
            tmp.replace(path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
