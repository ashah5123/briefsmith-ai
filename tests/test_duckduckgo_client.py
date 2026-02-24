"""Tests for DuckDuckGo search client: parsing, max_results, dedupe, normalization."""

from pathlib import Path
from unittest.mock import patch

from briefsmith.schemas import SourceItem
from briefsmith.tools import DuckDuckGoSearchClient, normalize_url

FAKE_HTML = """
<html>
<body>
<div class="result">
  <a class="result__a" href="https://example.com/page?utm_source=test">Example</a>
  <div class="result__snippet">First snippet here.</div>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/page?utm_medium=email">Example</a>
  <div class="result__snippet">Duplicate URL different utm.</div>
</div>
<div class="result">
  <a class="result__a" href="https://other.com/path/">Other</a>
  <div class="result__snippet">Second result snippet.</div>
</div>
<div class="result">
  <a class="result__a" href="https://third.org">Third</a>
  <div class="result__snippet">Third snippet.</div>
</div>
</body>
</html>
"""


@patch("briefsmith.tools.duckduckgo.requests.post")
def test_parsing_and_max_results(mock_post: object) -> None:
    """Correct parsing of link, title, snippet; max_results respected."""
    mock_post.return_value.text = FAKE_HTML
    mock_post.return_value.raise_for_status = lambda: None

    client = DuckDuckGoSearchClient(cache=None)
    results = client.search("test query", max_results=2)

    assert len(results) == 2
    assert all(isinstance(r, SourceItem) for r in results)
    assert results[0].url == "https://example.com/page"
    assert results[0].title == "Example"
    assert results[0].snippet == "First snippet here."
    assert results[1].url == "https://other.com/path"
    assert results[1].snippet == "Second result snippet."


@patch("briefsmith.tools.duckduckgo.requests.post")
def test_deduplication_by_url(mock_post: object) -> None:
    """Same URL with different utm params is deduplicated."""
    mock_post.return_value.text = FAKE_HTML
    mock_post.return_value.raise_for_status = lambda: None

    client = DuckDuckGoSearchClient(cache=None)
    results = client.search("test", max_results=10)

    urls = [r.url for r in results]
    assert urls.count("https://example.com/page") == 1
    assert "https://other.com/path" in urls
    assert "https://third.org" in urls


@patch("briefsmith.tools.duckduckgo.requests.post")
def test_normalization_removes_utm_params(mock_post: object) -> None:
    """Normalized URLs have utm_* params stripped."""
    mock_post.return_value.text = FAKE_HTML
    mock_post.return_value.raise_for_status = lambda: None

    client = DuckDuckGoSearchClient(cache=None)
    results = client.search("test", max_results=5)

    first = results[0]
    assert "utm_source" not in first.url
    assert "utm_medium" not in first.url
    assert first.url == "https://example.com/page"


def test_normalize_url_utils() -> None:
    """normalize_url strips utm params and trailing slash."""
    u = "https://site.com/path/?utm_source=foo&keep=1"
    assert normalize_url(u) == "https://site.com/path?keep=1"
    assert normalize_url("https://site.com/bar/") == "https://site.com/bar"


@patch("briefsmith.tools.duckduckgo.requests.post")
def test_cache_hit_skips_request(mock_post: object, tmp_path: Path) -> None:
    """When cache is used and hit, no request is made."""
    from briefsmith.tools import SearchCache

    cache = SearchCache(cache_dir=tmp_path)
    cached_items = [
        SourceItem(url="https://cached.com", title="C", snippet="Cached"),
    ]
    cache.set("cached query", cached_items)

    client = DuckDuckGoSearchClient(cache=cache)
    results = client.search("cached query", max_results=5)

    assert results == cached_items
    mock_post.assert_not_called()


@patch("briefsmith.tools.duckduckgo.requests.post")
def test_relative_url_resolved(mock_post: object) -> None:
    """Relative href is resolved against base (use non-DDG base so link is kept)."""
    html = """
    <html><body>
    <div class="result">
      <a class="result__a" href="/page">Target</a>
      <div class="result__snippet">Snippet</div>
    </div>
    </body></html>
    """
    mock_post.return_value.text = html
    mock_post.return_value.raise_for_status = lambda: None

    client = DuckDuckGoSearchClient(
        cache=None,
        base_url="https://example.com/search",
    )
    results = client.search("q", max_results=5)

    assert len(results) == 1
    assert results[0].url == "https://example.com/page"
    assert results[0].snippet == "Snippet"
