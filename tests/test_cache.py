"""Tests for search cache: write/read, SHA filename, JSON structure."""

import hashlib
import json
from pathlib import Path

from briefsmith.schemas import SourceItem
from briefsmith.tools import SearchCache


def test_cache_write_read(tmp_path: Path) -> None:
    """Write then read returns same SourceItems."""
    cache = SearchCache(cache_dir=tmp_path)
    items = [
        SourceItem(url="https://a.com", title="A", snippet="S1"),
        SourceItem(url="https://b.com", title="B", snippet="S2"),
    ]
    cache.set("my query", items)
    out = cache.get("my query")
    assert out is not None
    assert len(out) == 2
    assert out[0].url == "https://a.com"
    assert out[0].title == "A"
    assert out[1].snippet == "S2"


def test_cache_sha_filename(tmp_path: Path) -> None:
    """Cache file is named by SHA256 of query."""
    cache = SearchCache(cache_dir=tmp_path)
    query = "hello world"
    expected_sha = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    expected_path = tmp_path / f"{expected_sha}.json"
    cache.set(query, [SourceItem(url="https://x.com", snippet="")])
    assert expected_path.exists()
    assert cache.get(query) is not None


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    """Unknown query returns None."""
    cache = SearchCache(cache_dir=tmp_path)
    assert cache.get("nonexistent query") is None


def test_cache_json_structure_valid(tmp_path: Path) -> None:
    """Stored file is valid JSON and list of objects."""
    cache = SearchCache(cache_dir=tmp_path)
    items = [
        SourceItem(url="https://u.com", title="T", snippet="S"),
    ]
    cache.set("q", items)
    path = tmp_path / f"{hashlib.sha256(b'q').hexdigest()}.json"
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["url"] == "https://u.com"
    assert data[0]["title"] == "T"
    assert data[0]["snippet"] == "S"
    assert "accessed_at" in data[0]
